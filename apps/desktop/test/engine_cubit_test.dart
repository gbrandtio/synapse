import 'dart:async';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:synapse_desktop/core/result.dart';
import 'package:synapse_desktop/engine/engine_cubit.dart';
import 'package:synapse_desktop/engine/engine_process.dart';

import 'fake_engine.dart';

final class _FakeLauncher implements EngineLauncher {
  _FakeLauncher(this.results);

  final List<Result<RunningEngine>> results;

  @override
  Future<Result<RunningEngine>> start() async => results.removeAt(0);
}

final class _HeldLauncher implements EngineLauncher {
  _HeldLauncher(this.result);

  final Future<Result<RunningEngine>> result;

  @override
  Future<Result<RunningEngine>> start() => result;
}

final class _QueueLauncher implements EngineLauncher {
  _QueueLauncher(this.results);

  final List<Future<Result<RunningEngine>>> results;

  @override
  Future<Result<RunningEngine>> start() => results.removeAt(0);
}

final class _CountingLauncher implements EngineLauncher {
  _CountingLauncher(this.next);

  final Future<Result<RunningEngine>> Function() next;

  @override
  Future<Result<RunningEngine>> start() => next();
}

void main() {
  final client = fakeClient({});

  blocTest<EngineCubit, EngineState>(
    'a failure can be retried',
    build: () => EngineCubit(
      _FakeLauncher([
        const Failure('Synapse could not start its engine.'),
        Success(RunningEngine(client, () async {})),
      ]),
    ),
    act: (cubit) async {
      await cubit.start();
      await cubit.start();
    },
    expect: () => [
      const EngineStarting(),
      const EngineFailed('Synapse could not start its engine.'),
      const EngineStarting(),
      EngineReady(client),
    ],
  );

  test('an engine that finishes starting after close is stopped', () async {
    var stopped = false;
    final started = Completer<Result<RunningEngine>>();
    final cubit = EngineCubit(_HeldLauncher(started.future));
    final starting = cubit.start();
    await cubit.close();
    started.complete(
      Success(RunningEngine(client, () async => stopped = true)),
    );
    await starting;
    expect(stopped, isTrue);
  });

  test('a failure after close does not throw', () async {
    final started = Completer<Result<RunningEngine>>();
    final cubit = EngineCubit(_HeldLauncher(started.future));
    final starting = cubit.start();
    await cubit.close();
    started.complete(const Failure('late'));
    await starting;
  });

  test('a crashed engine restarts, and says so', () async {
    final crash = Completer<void>();
    final replacement = fakeClient({});
    final cubit = EngineCubit(
      _FakeLauncher([
        Success(RunningEngine(client, () async {}, exited: crash.future)),
        Success(RunningEngine(replacement, () async {})),
      ]),
    );
    await cubit.start();
    expect(cubit.state, EngineReady(client));
    crash.complete();
    await Future<void>.delayed(Duration.zero);
    expect(cubit.state, EngineReady(replacement, restarted: true));
    await cubit.close();
  });

  test('an engine that keeps crashing stops being restarted', () async {
    RunningEngine crashing() =>
        RunningEngine(client, () async {}, exited: Future<void>.value());
    final cubit = EngineCubit(
      _FakeLauncher([
        Success(crashing()),
        Success(crashing()),
        Success(crashing()),
      ]),
    );
    await cubit.start();
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(cubit.state, isA<EngineFailed>());
    await cubit.close();
  });

  test('stopping on close is not treated as a crash', () async {
    final exit = Completer<void>();
    final cubit = EngineCubit(
      _FakeLauncher([
        Success(
          RunningEngine(
            client,
            () async => exit.complete(),
            exited: exit.future,
          ),
        ),
      ]),
    );
    await cubit.start();
    await cubit.close();
    await Future<void>.delayed(Duration.zero);
    expect(cubit.state, EngineReady(client));
  });

  test('closing during a restart stops the new engine too', () async {
    final crash = Completer<void>();
    final replacement = Completer<Result<RunningEngine>>();
    final stopDone = Completer<void>();
    var newEngineStopped = false;
    final cubit = EngineCubit(
      _QueueLauncher([
        Future.value(
          Success(
            RunningEngine(client, () => stopDone.future, exited: crash.future),
          ),
        ),
        replacement.future,
      ]),
    );
    await cubit.start();
    crash.complete();
    await Future<void>.delayed(Duration.zero);
    final closing = cubit.close();
    replacement.complete(
      Success(RunningEngine(client, () async => newEngineStopped = true)),
    );
    await Future<void>.delayed(Duration.zero);
    stopDone.complete();
    await closing;
    expect(newEngineStopped, isTrue);
  });

  test('a second start while one is running does nothing', () async {
    var starts = 0;
    final held = Completer<Result<RunningEngine>>();
    final cubit = EngineCubit(
      _CountingLauncher(() {
        starts++;
        return held.future;
      }),
    );
    final first = cubit.start();
    await cubit.start();
    expect(starts, 1);
    held.complete(Success(RunningEngine(client, () async {})));
    await first;
    await cubit.start();
    expect(starts, 1);
    await cubit.close();
  });

  test('a launcher that throws becomes a failure with a retry', () async {
    final cubit = EngineCubit(
      _CountingLauncher(() => throw Exception('no data folder')),
    );
    await cubit.start();
    expect(cubit.state, isA<EngineFailed>());
    await cubit.close();
  });

  test('a launcher that throws after closing stays quiet', () async {
    final held = Completer<Result<RunningEngine>>();
    final cubit = EngineCubit(_CountingLauncher(() => held.future));
    final starting = cubit.start();
    await cubit.close();
    held.completeError(Exception('late'));
    await starting;
  });

  test('closing stops the engine', () async {
    var stopped = false;
    final cubit = EngineCubit(
      _FakeLauncher([
        Success(RunningEngine(client, () async => stopped = true)),
      ]),
    );
    await cubit.start();
    await cubit.close();
    expect(stopped, isTrue);
  });
}
