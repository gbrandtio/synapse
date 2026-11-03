import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:synapse_desktop/documents/documents_bloc.dart';
import 'package:synapse_desktop/engine/engine_process.dart';
import 'package:synapse_desktop/main.dart';
import 'package:synapse_desktop/ui/home_page.dart';

/// Runs the real app against the real bundled engine and AI model.
///
/// Set SYNAPSE_RESOURCES to the bundle's engine folder and SYNAPSE_TEST_PDF to
/// a PDF saying backups are kept for 14 days.
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  Future<void> waitFor(
    WidgetTester tester,
    Finder finder, {
    Duration limit = const Duration(minutes: 2),
  }) async {
    final deadline = DateTime.now().add(limit);
    while (finder.evaluate().isEmpty) {
      if (DateTime.now().isAfter(deadline)) {
        fail('Timed out waiting for $finder');
      }
      await tester.pump(const Duration(milliseconds: 200));
    }
  }

  testWidgets('add a PDF, ask a question, get a cited answer', (tester) async {
    final temp = await Directory.systemTemp.createTemp('synapse-app-test');
    addTearDown(() => temp.delete(recursive: true));
    await tester.pumpWidget(
      SynapseApp(
        launcher: ProcessEngineLauncher(
          EnginePaths.bundled(),
          dataDir: () async => temp,
        ),
      ),
    );
    await waitFor(tester, find.text('Drop PDF files here'));

    final panel = tester.element(find.byType(DocumentsPanel));
    panel.read<DocumentsBloc>().add(
      DocumentsDropped([Platform.environment['SYNAPSE_TEST_PDF']!]),
    );
    await waitFor(tester, find.text('guide.pdf'));

    await tester.enterText(
      find.byType(TextField),
      'How long are backups kept?',
    );
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await waitFor(tester, find.textContaining('guide.pdf, page 1'));

    final answer = tester.widgetList<SelectableText>(
      find.byType(SelectableText),
    );
    expect(answer.first.data, contains('14'));
  });
}
