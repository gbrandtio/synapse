import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'engine/engine_cubit.dart';
import 'engine/engine_process.dart';
import 'ui/home_page.dart';
import 'ui/theme.dart';

void main() {
  runApp(SynapseApp(launcher: ProcessEngineLauncher(EnginePaths.bundled())));
}

/// The Synapse desktop app.
class SynapseApp extends StatefulWidget {
  /// Creates the app, starting the engine with [launcher].
  const SynapseApp({required this.launcher, super.key});

  /// Starts the engine.
  final EngineLauncher launcher;

  @override
  State<SynapseApp> createState() => _SynapseAppState();
}

class _SynapseAppState extends State<SynapseApp> {
  late final EngineCubit _engine = EngineCubit(widget.launcher)..start();

  @override
  void dispose() {
    _engine.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider.value(
      value: _engine,
      child: MaterialApp(
        title: 'Synapse',
        debugShowCheckedModeBanner: false,
        theme: synapseTheme(),
        home: const HomePage(),
      ),
    );
  }
}
