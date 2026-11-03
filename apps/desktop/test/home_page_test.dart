import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:synapse_desktop/core/result.dart';
import 'package:synapse_desktop/documents/documents_bloc.dart';
import 'package:synapse_desktop/engine/engine_client.dart';
import 'package:synapse_desktop/engine/engine_cubit.dart';
import 'package:synapse_desktop/engine/engine_process.dart';
import 'package:synapse_desktop/ui/home_page.dart';

import 'fake_engine.dart';

final class _Launcher implements EngineLauncher {
  _Launcher(this.result);

  final Result<RunningEngine> result;

  @override
  Future<Result<RunningEngine>> start() async => result;
}

final class _SequenceLauncher implements EngineLauncher {
  _SequenceLauncher(this.results);

  final List<Result<RunningEngine>> results;

  @override
  Future<Result<RunningEngine>> start() async => results.removeAt(0);
}

final class _HeldClient extends http.BaseClient {
  _HeldClient(this.reply);

  final Completer<http.StreamedResponse> reply;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) => reply.future;
}

Widget _app(EngineCubit cubit) => BlocProvider.value(
  value: cubit,
  child: const MaterialApp(home: HomePage()),
);

void main() {
  testWidgets('shows sources after asking, including an inferred one', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1400, 1000);
    addTearDown(tester.view.resetPhysicalSize);
    final client = fakeClient({
      '/ask': sse([
        ('token', {'text': 'Firmware 2.1.7.'}),
        (
          'citations',
          {
            'citations': [
              {
                'number': 1,
                'document_name': 'guide.pdf',
                'page': 2,
                'text': 'x',
                'is_inferred': true,
              },
            ],
          },
        ),
      ]),
    });
    final cubit = EngineCubit(
      _Launcher(Success(RunningEngine(client, () async {}))),
    );
    await tester.pumpWidget(_app(cubit));
    await tester.runAsync(cubit.start);
    await tester.pump();
    expect(find.text('Drop PDF files here'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'Which firmware?');
    await tester.runAsync(() async {
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await Future<void>.delayed(const Duration(milliseconds: 50));
    });
    await tester.pumpAndSettle();
    expect(find.text('Which firmware?'), findsOneWidget);
    expect(find.text('Firmware 2.1.7.'), findsOneWidget);
    expect(find.text('Likely source: guide.pdf, page 2'), findsOneWidget);
  });

  testWidgets('a start failure offers a retry that works', (tester) async {
    final client = fakeClient({'/documents': http.Response('[]', 200)});
    final cubit = EngineCubit(
      _SequenceLauncher([
        const Failure('Could not start.'),
        Success(RunningEngine(client, () async {})),
      ]),
    );
    await tester.pumpWidget(_app(cubit));
    await tester.runAsync(cubit.start);
    await tester.pump();
    expect(find.text('Could not start.'), findsOneWidget);
    await tester.tap(find.text('Try again'));
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 50)),
    );
    await tester.pump();
    expect(find.text('Drop PDF files here'), findsOneWidget);
  });

  testWidgets('shows starting, documents, a real citation and problems', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1400, 1000);
    addTearDown(tester.view.resetPhysicalSize);
    final client = fakeClient({
      '/documents': http.Response(
        '[{"id":1,"name":"guide.pdf","pages":3,"passages":3}]',
        200,
      ),
      '/ask': sse([
        ('token', {'text': 'Yes [1].'}),
        (
          'citations',
          {
            'citations': [
              {
                'number': 1,
                'document_name': 'guide.pdf',
                'page': 2,
                'text': 'x',
                'is_inferred': false,
              },
            ],
          },
        ),
        ('error', {'message': 'Later problem.'}),
      ]),
    });
    final cubit = EngineCubit(
      _Launcher(Success(RunningEngine(client, () async {}))),
    );
    await tester.pumpWidget(_app(cubit));
    expect(find.text('Starting Synapse...'), findsOneWidget);
    await tester.runAsync(cubit.start);
    await tester.pump();
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 50)),
    );
    await tester.pump();
    expect(find.text('guide.pdf'), findsOneWidget);
    expect(find.text('3 pages'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'Question');
    await tester.tap(find.byTooltip('Send'));
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 50)),
    );
    await tester.pumpAndSettle();
    expect(find.text('[1] guide.pdf, page 2'), findsOneWidget);
    expect(find.text('Later problem.'), findsOneWidget);
  });

  testWidgets('Send keeps the typed question while an answer is written', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1400, 1000);
    addTearDown(tester.view.resetPhysicalSize);
    final reply = Completer<http.StreamedResponse>();
    final client = EngineClient(
      baseUrl: Uri.parse('http://127.0.0.1:1'),
      token: 'test',
      httpClient: _HeldClient(reply),
    );
    final cubit = EngineCubit(
      _Launcher(Success(RunningEngine(client, () async {}))),
    );
    await tester.pumpWidget(_app(cubit));
    await tester.runAsync(cubit.start);
    await tester.pump();

    await tester.enterText(find.byType(TextField), 'first');
    await tester.tap(find.byTooltip('Send'));
    await tester.pump();
    await tester.pump();
    await tester.enterText(find.byType(TextField), 'second');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pump();
    expect(find.text('second'), findsOneWidget);
    final send = tester.widget<IconButton>(
      find.widgetWithIcon(IconButton, Icons.send),
    );
    expect(send.onPressed, isNull);
  });

  testWidgets('shows progress and problems while adding a file', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1400, 1000);
    addTearDown(tester.view.resetPhysicalSize);
    final bloc = DocumentsBloc(fakeClient({}));
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: BlocProvider.value(value: bloc, child: const DocumentsPanel()),
        ),
      ),
    );
    bloc.emit(const DocumentsState(progress: 'Reading a.pdf', error: 'Oops.'));
    await tester.pump();
    expect(find.text('Reading a.pdf'), findsOneWidget);
    expect(find.text('Oops.'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
  });
}
