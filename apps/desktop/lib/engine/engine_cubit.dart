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
  const EngineReady(this.client);

  /// The connected client.
  final EngineClient client;

  @override
  List<Object?> get props => [client];
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

/// Starts the engine and stops it when the app closes.
final class EngineCubit extends Cubit<EngineState> {
  /// Creates the cubit.
  EngineCubit(this._launcher) : super(const EngineStarting());

  final EngineLauncher _launcher;
  RunningEngine? _engine;

  /// Starts the engine, or tries again after a failure.
  Future<void> start() async {
    emit(const EngineStarting());
    switch (await _launcher.start()) {
      case Success<RunningEngine>(:final value):
        if (isClosed) {
          await value.stop();
          return;
        }
        _engine = value;
        emit(EngineReady(value.client));
      case Failure<RunningEngine>(:final message):
        if (!isClosed) {
          emit(EngineFailed(message));
        }
    }
  }

  @override
  Future<void> close() async {
    await _engine?.stop();
    return super.close();
  }
}
