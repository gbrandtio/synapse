import 'package:flutter/material.dart';

/// The only colours the app uses: black on white, with greys for quieter text.
abstract final class SynapseColors {
  /// Main text and the few filled controls.
  static const ink = Color(0xFF111111);

  /// Quieter text such as hints and page counts.
  static const muted = Color(0xFF6B7280);

  /// Thin lines around and between things.
  static const line = Color(0xFFE5E7EB);

  /// A very light grey, for hover and selection.
  static const wash = Color(0xFFF5F5F5);

  /// Problems the user should notice.
  static const problem = Color(0xFFB42318);
}

/// Builds the minimal white theme, using the bundled Poppins font.
ThemeData synapseTheme() {
  const scheme = ColorScheme.light(
    primary: SynapseColors.ink,
    onPrimary: Colors.white,
    secondary: SynapseColors.ink,
    surface: Colors.white,
    onSurface: SynapseColors.ink,
    outline: SynapseColors.line,
    outlineVariant: SynapseColors.line,
    error: SynapseColors.problem,
    surfaceTint: Colors.transparent,
  );
  const text = TextTheme(
    headlineSmall: TextStyle(
      fontSize: 26,
      fontWeight: FontWeight.w300,
      height: 1.3,
    ),
    titleMedium: TextStyle(
      fontSize: 18,
      fontWeight: FontWeight.w600,
      letterSpacing: -0.2,
    ),
    titleSmall: TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
    bodyMedium: TextStyle(fontSize: 14, height: 1.65),
    bodySmall: TextStyle(fontSize: 12, height: 1.5, color: SynapseColors.muted),
    labelSmall: TextStyle(
      fontSize: 12,
      fontWeight: FontWeight.w500,
      color: SynapseColors.muted,
      letterSpacing: 0.2,
    ),
  );
  return ThemeData(
    useMaterial3: true,
    fontFamily: 'Poppins',
    colorScheme: scheme,
    scaffoldBackgroundColor: Colors.white,
    canvasColor: Colors.white,
    textTheme: text,
    dividerTheme: const DividerThemeData(
      color: SynapseColors.line,
      space: 1,
      thickness: 1,
    ),
    hoverColor: SynapseColors.wash,
    highlightColor: Colors.transparent,
    splashFactory: NoSplash.splashFactory,
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: SynapseColors.ink,
      linearTrackColor: SynapseColors.line,
      linearMinHeight: 2,
      strokeWidth: 2,
    ),
    textSelectionTheme: const TextSelectionThemeData(
      cursorColor: SynapseColors.ink,
      selectionColor: SynapseColors.line,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        elevation: 0,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: SynapseColors.muted,
        textStyle: const TextStyle(fontSize: 12, fontFamily: 'Poppins'),
        padding: EdgeInsets.zero,
        minimumSize: const Size(0, 32),
        alignment: Alignment.centerLeft,
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: Colors.white,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: SynapseColors.line),
      ),
    ),
    expansionTileTheme: const ExpansionTileThemeData(
      shape: Border(),
      collapsedShape: Border(),
      iconColor: SynapseColors.muted,
      collapsedIconColor: SynapseColors.muted,
      tilePadding: EdgeInsets.zero,
      childrenPadding: EdgeInsets.only(bottom: 12),
      expandedAlignment: Alignment.centerLeft,
    ),
  );
}
