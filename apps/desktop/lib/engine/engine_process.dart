import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

import '../core/result.dart';
import 'engine_client.dart';

/// A running engine.
final class RunningEngine {
  /// Creates a handle to a running engine.
  const RunningEngine(this.client, this.stop);

  /// The client connected to it.
  final EngineClient client;

  /// Stops the engine.
  final Future<void> Function() stop;
}

/// Starts the engine.
abstract interface class EngineLauncher {
  /// Starts the engine and connects to it.
  Future<Result<RunningEngine>> start();
}

/// Where the engine and its bundled parts live.
final class EnginePaths {
  /// Creates a set of paths.
  const EnginePaths({
    required this.python,
    required this.engineDir,
    required this.embeddingDir,
    required this.ollamaBinary,
    required this.ollamaModels,
  });

  /// Finds the parts inside the installed app, beside the executable.
  ///
  /// Set `SYNAPSE_RESOURCES` to run against a build folder during development.
  factory EnginePaths.bundled() {
    final executable = File(Platform.resolvedExecutable).parent;
    final override = kDebugMode
        ? Platform.environment['SYNAPSE_RESOURCES']
        : null;
    final root =
        override ??
        (Platform.isMacOS
            ? '${executable.parent.path}/Resources/engine'
            : '${executable.path}/engine');
    final isWindows = Platform.isWindows;
    return EnginePaths(
      python: isWindows
          ? '$root/python/python.exe'
          : '$root/python/bin/python3',
      engineDir: '$root/site-packages',
      embeddingDir: '$root/models/embedding',
      ollamaBinary: isWindows
          ? '$root/ollama/ollama.exe'
          : '$root/ollama/ollama',
      ollamaModels: '$root/models/ollama',
    );
  }

  /// The Python interpreter.
  final String python;

  /// The folder holding the engine's packages.
  final String engineDir;

  /// The folder holding the embedding model.
  final String embeddingDir;

  /// The Ollama program.
  final String ollamaBinary;

  /// The folder holding the AI model.
  final String ollamaModels;
}

/// Starts the bundled engine as a child process.
///
/// The token goes through stdin, so it never appears in process lists. The
/// engine exits by itself when stdin closes, so no orphan process remains.
final class ProcessEngineLauncher implements EngineLauncher {
  /// Creates a launcher.
  const ProcessEngineLauncher(
    this._paths, {
    this.dataDir = getApplicationSupportDirectory,
  });

  static const _readyTimeout = Duration(seconds: 60);

  final EnginePaths _paths;

  /// Finds the folder for the user's data.
  final Future<Directory> Function() dataDir;

  @override
  Future<Result<RunningEngine>> start() async {
    final Process process;
    try {
      final data = await dataDir();
      process = await Process.start(
        _paths.python,
        ['-I', '-c', _bootstrap(_paths.engineDir)],
        environment: {
          'SYNAPSE_DATA_DIR': data.path,
          'SYNAPSE_EMBEDDING_DIR': _paths.embeddingDir,
          'SYNAPSE_OLLAMA_BIN': _paths.ollamaBinary,
          'SYNAPSE_OLLAMA_MODELS': _paths.ollamaModels,
          'HF_HUB_OFFLINE': '1',
          'HF_HUB_DISABLE_TELEMETRY': '1',
          'PYTHONDONTWRITEBYTECODE': '1',
          ..._keptEnvironment(),
        },
        includeParentEnvironment: false,
      );
    } on ProcessException {
      return const Failure('Synapse could not start its engine.');
    }
    final token = _newToken();
    process.stdin.writeln(token);
    await process.stdin.flush();
    unawaited(process.stderr.drain<void>());
    final port = await _readPort(process);
    if (port == null) {
      process.kill();
      return const Failure('Synapse could not start its engine.');
    }
    return Success(
      RunningEngine(
        EngineClient(
          baseUrl: Uri.parse('http://127.0.0.1:$port'),
          token: token,
        ),
        () async {
          await process.stdin.close();
          await process.exitCode.timeout(
            const Duration(seconds: 5),
            onTimeout: () {
              process.kill(ProcessSignal.sigkill);
              return -1;
            },
          );
        },
      ),
    );
  }

  // Keeps reading after the first line, because closing this pipe would make
  // the engine fail the next time anything prints to stdout.
  Future<int?> _readPort(Process process) {
    final port = Completer<int?>();
    process.stdout
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen(
          (line) {
            if (!port.isCompleted) {
              port.complete(_portFrom(line));
            }
          },
          onDone: () {
            if (!port.isCompleted) {
              port.complete(null);
            }
          },
        );
    return port.future.timeout(_readyTimeout, onTimeout: () => null);
  }

  int? _portFrom(String line) {
    try {
      final message = jsonDecode(line);
      if (message case {'event': 'ready', 'port': final int port}) {
        return port;
      }
    } on FormatException {
      return null;
    }
    return null;
  }

  // Only what programs need to run. Leaving out the rest keeps proxy settings
  // and anything else unexpected away from the engine.
  Map<String, String> _keptEnvironment() {
    const names = {
      'HOME',
      'PATH',
      'TMPDIR',
      'USERPROFILE',
      'SYSTEMROOT',
      'TEMP',
      'TMP',
      'APPDATA',
      'LOCALAPPDATA',
      'PROGRAMDATA',
    };
    return {
      for (final entry in Platform.environment.entries)
        if (names.contains(entry.key)) entry.key: entry.value,
    };
  }

  String _newToken() {
    final random = Random.secure();
    final bytes = List<int>.generate(32, (_) => random.nextInt(256));
    return base64UrlEncode(bytes);
  }

  // `-I` ignores the environment and the current folder, so nothing planted
  // beside the app can be imported. The packages folder is added explicitly.
  String _bootstrap(String engineDir) {
    final quoted = jsonEncode(engineDir);
    return 'import sys; sys.path.insert(0, $quoted); '
        'from synapse_engine.__main__ import main; main()';
  }
}
