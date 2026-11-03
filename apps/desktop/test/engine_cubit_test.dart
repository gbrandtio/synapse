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
