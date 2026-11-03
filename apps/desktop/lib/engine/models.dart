import 'package:equatable/equatable.dart';

/// A document stored in the knowledge base.
final class DocumentInfo extends Equatable {
  /// Creates a document description.
  const DocumentInfo({
    required this.id,
    required this.name,
    required this.pages,
    required this.passages,
  });

  /// Reads a document from the engine's JSON.
  factory DocumentInfo.fromJson(Map<String, Object?> json) => DocumentInfo(
    id: json['id']! as int,
    name: json['name']! as String,
    pages: json['pages']! as int,
    passages: json['passages']! as int,
  );

  /// The engine's identifier.
  final int id;

  /// The file name.
  final String name;

  /// How many pages it has.
  final int pages;

  /// How many searchable passages it became.
  final int passages;

  @override
  List<Object?> get props => [id, name, pages, passages];
}

/// A numbered source for an answer.
final class Citation extends Equatable {
  /// Creates a citation.
  const Citation({
    required this.number,
    required this.documentName,
    required this.page,
    required this.text,
    required this.isInferred,
  });

  /// Reads a citation from the engine's JSON.
  factory Citation.fromJson(Map<String, Object?> json) => Citation(
    number: json['number']! as int,
    documentName: json['document_name']! as String,
    page: json['page']! as int,
    text: json['text']! as String,
    isInferred: json['is_inferred']! as bool,
  );

  /// The number used in the answer text.
  final int number;

  /// The document it came from.
  final String documentName;

  /// The page it came from.
  final int page;

  /// The passage text.
  final String text;

  /// Whether the app added this because the AI cited nothing.
  final bool isInferred;

  @override
  List<Object?> get props => [number, documentName, page, text, isInferred];
}

/// One step of adding a document.
sealed class IngestUpdate {
  const IngestUpdate();
}

/// Plain-language progress.
final class IngestProgress extends IngestUpdate {
  /// Creates a progress update.
  const IngestProgress(this.message, this.done, this.total);

  /// What is happening now.
  final String message;

  /// Passages finished.
  final int done;

  /// Passages in total, or zero when not yet known.
  final int total;
}

/// The document is ready.
final class IngestFinished extends IngestUpdate {
  /// Creates a finished update.
  const IngestFinished(this.document, {required this.alreadyPresent});

  /// The stored document.
  final DocumentInfo document;

  /// Whether this exact file had already been added.
  final bool alreadyPresent;
}

/// Adding the document failed.
final class IngestFailed extends IngestUpdate {
  /// Creates a failure update.
  const IngestFailed(this.message);

  /// A plain explanation for the user.
  final String message;
}

/// One step of answering a question.
sealed class AnswerUpdate {
  const AnswerUpdate();
}

/// A piece of answer text.
final class AnswerToken extends AnswerUpdate {
  /// Creates a token update.
  const AnswerToken(this.text);

  /// The text to append.
  final String text;
}

/// The sources for the finished answer.
final class AnswerCitations extends AnswerUpdate {
  /// Creates a citations update.
  const AnswerCitations(this.citations);

  /// The sources.
  final List<Citation> citations;
}

/// Nothing reliable was found.
final class AnswerNotFound extends AnswerUpdate {
  /// Creates a not-found update.
  const AnswerNotFound(this.message);

  /// The message to show.
  final String message;
}

/// Answering failed.
final class AnswerFailed extends AnswerUpdate {
  /// Creates a failure update.
  const AnswerFailed(this.message);

  /// A plain explanation for the user.
  final String message;
}
