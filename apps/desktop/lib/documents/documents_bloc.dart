import 'dart:async';

import 'package:bloc_concurrency/bloc_concurrency.dart';
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../core/result.dart';
import '../engine/engine_client.dart';
import '../engine/models.dart';

const _couldNotAdd = 'Something went wrong while adding a file.';

/// Something that happened to the document list.
sealed class DocumentsEvent {
  const DocumentsEvent();
}

/// Load the stored documents.
final class DocumentsLoaded extends DocumentsEvent {
  /// Creates the event.
  const DocumentsLoaded();
}

/// The user added files.
final class DocumentsDropped extends DocumentsEvent {
  /// Creates the event.
  const DocumentsDropped(this.paths);

  /// The files to add.
  final List<String> paths;
}

/// What the document area shows.
final class DocumentsState extends Equatable {
  /// Creates the state.
  const DocumentsState({this.documents = const [], this.progress, this.error});

  /// The stored documents.
  final List<DocumentInfo> documents;

  /// What is being processed now, if anything.
  final String? progress;

  /// The latest problem, if any.
  final String? error;

  @override
  List<Object?> get props => [documents, progress, error];
}

/// Adds documents one at a time and keeps the list current.
final class DocumentsBloc extends Bloc<DocumentsEvent, DocumentsState> {
  /// Creates the bloc.
  DocumentsBloc(this._client) : super(const DocumentsState()) {
    on<DocumentsLoaded>(_onLoaded, transformer: droppable());
    // Sequential, because each drop must finish adding before the next starts.
    on<DocumentsDropped>(_onDropped, transformer: sequential());
  }

  final EngineClient _client;

  Future<void> _onLoaded(
    DocumentsLoaded event,
    Emitter<DocumentsState> emit,
  ) async {
    switch (await _client.listDocuments()) {
      case Success<List<DocumentInfo>>(:final value):
        emit(DocumentsState(documents: value));
      case Failure<List<DocumentInfo>>(:final message):
        emit(DocumentsState(documents: state.documents, error: message));
    }
  }

  Future<void> _onDropped(
    DocumentsDropped event,
    Emitter<DocumentsState> emit,
  ) async {
    if (state.error != null) {
      emit(DocumentsState(documents: state.documents));
    }
    for (final path in event.paths) {
      await emit.forEach<IngestUpdate>(
        _client.addDocument(path),
        onData: _applyUpdate,
        onError: (_, _) => _withError(_couldNotAdd),
      );
    }
  }

  DocumentsState _applyUpdate(IngestUpdate update) {
    return switch (update) {
      IngestProgress(:final message, :final done, :final total) =>
        DocumentsState(
          documents: state.documents,
          progress: total == 0 ? message : '$message: $done of $total passages',
          error: state.error,
        ),
      IngestFinished(:final document, alreadyPresent: true) => _withError(
        '${document.name} is already in your documents.',
      ),
      IngestFinished(:final document) => DocumentsState(
        documents: [document, ...state.documents],
        error: state.error,
      ),
      IngestFailed(:final message) => _withError(message),
    };
  }

  // Problems add up, so one file's failure stays visible while others finish.
  DocumentsState _withError(String message) => DocumentsState(
    documents: state.documents,
    error: state.error == null ? message : '${state.error}\n$message',
  );
}
