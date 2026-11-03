import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:synapse_desktop/core/result.dart';
import 'package:synapse_desktop/engine/engine_process.dart';

Future<ProcessEngineLauncher> _launcherFor(String mainBody) async {
  final root = await Directory.systemTemp.createTemp('synapse-launcher');
  addTearDown(() => root.delete(recursive: true));
  final package = Directory('${root.path}/synapse_engine/__main__.py');
  await File(package.path).create(recursive: true);
  await File(package.path).writeAsString(mainBody);
  return ProcessEngineLauncher(
    EnginePaths(
      python: 'python3',
      engineDir: root.path,
      embeddingDir: '/x',
      llamaBinary: '/x',
      aiModelFile: '/x',
    ),
    dataDir: () async => root,
  );
}

void main() {
  test('a missing engine reports a friendly failure', () async {
    final launcher = ProcessEngineLauncher(
      const EnginePaths(
        python: '/nonexistent/python3',
        engineDir: '/nonexistent',
        embeddingDir: '/nonexistent',
        llamaBinary: '/nonexistent',
        aiModelFile: '/nonexistent',
      ),
      dataDir: () async => Directory.systemTemp,
    );
    final result = await launcher.start();
    expect((result as Failure<RunningEngine>).message, contains('could not'));
  });

  test('sends a token, reads the port, and stops through stdin', () async {
    final launcher = await _launcherFor('''
import os, sys
def main():
    token = sys.stdin.readline().strip()
    assert len(token) >= 32
    assert "HTTP_PROXY" not in os.environ
    print('{"event": "ready", "port": 4242}', flush=True)
    print("later output must not break anything", flush=True)
    sys.stdin.read()
    print("still able to print at exit", flush=True)
''');
    final result = await launcher.start();
    final engine = (result as Success<RunningEngine>).value;
    expect(engine.client.baseUrl.port, 4242);
    await engine.stop();
  });

  test(
    'an engine that ignores the stop request is killed',
    () async {
      final launcher = await _launcherFor('''
import sys, time
def main():
    sys.stdin.readline()
    print('{"event": "ready", "port": 4242}', flush=True)
    time.sleep(60)
''');
      final result = await launcher.start();
      final engine = (result as Success<RunningEngine>).value;
      await engine.stop();
      await engine.exited;
    },
    timeout: const Timeout(Duration(seconds: 20)),
  );

  for (final (name, body) in [
    ('exits early', 'def main():\n    pass\n'),
    ('prints garbage', 'def main():\n    print("oops", flush=True)\n'),
    (
      'prints the wrong shape',
      'def main():\n    print(\'{"port": "x"}\', flush=True)\n',
    ),
  ]) {
    test('an engine that $name reports a failure', () async {
      final launcher = await _launcherFor(body);
      expect(await launcher.start(), isA<Failure<RunningEngine>>());
    });
  }

  test('bundled paths sit beside the app', () {
    final paths = EnginePaths.bundled();
    expect(paths.python, contains('python'));
    expect(paths.embeddingDir, endsWith('models/embedding'));
    expect(paths.aiModelFile, endsWith('.gguf'));
  });
}
