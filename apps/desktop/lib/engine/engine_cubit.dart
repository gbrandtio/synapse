import 'dart:async';

import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../core/result.dart';
import 'engine_client.dart';
import 'engine_process.dart';

/// The engine's status.
sealed class EngineState extends Equatable {
  const EngineState();

  @override
  List<Object?> get props => [];
}

/// The engine is starting.
final class EngineStarting extends EngineState {
  /// Creates the state.
  const EngineStarting();
}

/// The engine is ready to use.
final class EngineReady extends EngineState {
  /// Creates the state.
  const EngineReady(this.client, {this.restarted = false});

  /// The connected client.
  final EngineClient client;

  /// Whether this engine replaced one that stopped unexpectedly.
  final bool restarted;

  @override
  List<Object?> get props => [client, restarted];
}

/// The engine could not start.
final class EngineFailed extends EngineState {
  /// Creates the state.
  const EngineFailed(this.message);

  /// A plain explanation for the user.
  final String message;

  @override
  List<Object?> get props => [message];
}

/// Starts the engine, restarts it if it crashes, and stops it when the app
/// closes.
final class EngineCubit extends Cubit<EngineState> {
  /// Creates the cubit.
  EngineCubit(this._launcher) : super(const EngineStarting());

  // More crashes than this in the window means restarting isn't helping.
  static const _maxRestarts = 2;
  static const _restartWindow = Duration(minutes: 1);

  final EngineLauncher _launcher;
  final List<DateTime> _restarts = [];
  RunningEngine? _engine;
  bool _isClosing = false;
  bool _isStarting = false;

  /// Starts the engine, or tries again after a failure.
  Future<void> start() async {
    // Two engines would share one database, so a start only follows a failure
    // or begins the app.
    if (_isStarting || state is EngineReady) {
      return;
    }
    _restarts.clear();
    await _start();
  }

  void _onExit(RunningEngine engine) {
    if (_isClosing || isClosed || !identical(engine, _engine)) {
      return;
    }
    final now = DateTime.now();
    _restarts.removeWhere((t) => now.difference(t) > _restartWindow);
    if (_restarts.length >= _maxRestarts) {
      emit(
        const EngineFailed(
          'Synapse keeps stopping unexpectedly. Your documents are safe.',
        ),
      );
      return;
    }
    _restarts.add(now);
    unawaited(_start(restarted: true));
  }

  Future<void> _start({bool restarted = false}) async {
    _isStarting = true;
    emit(const EngineStarting());
    final Result<RunningEngine> result;
    try {
      result = await _launcher.start();
    } on Exception {
      _isStarting = false;
      if (!isClosed && !_isClosing) {
        emit(const EngineFailed('Synapse could not start its engine.'));
      }
      return;
    }
    _isStarting = false;
    switch (result) {
      case Success<RunningEngine>(:final value):
        if (isClosed || _isClosing) {
          await value.stop();
          return;
        }
        _engine = value;
        unawaited(value.exited?.then((_) => _onExit(value)));
        emit(EngineReady(value.client, restarted: restarted));
      case Failure<RunningEngine>(:final message):
        if (!isClosed && !_isClosing) {
          emit(EngineFailed(message));
        }
    }
  }

  @override
  Future<void> close() async {
    _isClosing = true;
    await _engine?.stop();
    return super.close();
  }
}
