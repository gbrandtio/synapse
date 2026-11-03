# Synapse desktop

The Flutter app. It starts the Python engine, shows the documents and the chat, and handles state with Bloc. The Dart package is named `synapse_desktop`, and the app is called Synapse.

- `lib/engine/` starts, watches and restarts the engine.
- `lib/ui/` holds the screens and the white theme.
- `assets/` holds the bundled Poppins font and the draft terms.

Run the tests with `flutter test --coverage`, and check the code with `flutter analyze`. To build the Mac app, see [Build for Mac](../../README.md#build-for-mac).
