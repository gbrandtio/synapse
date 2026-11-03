import 'package:desktop_drop/desktop_drop.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../chat/chat_bloc.dart';
import '../documents/documents_bloc.dart';
import '../engine/engine_client.dart';
import '../engine/engine_cubit.dart';
import '../engine/models.dart';

/// Shows start-up status, then the main screen.
class HomePage extends StatelessWidget {
  /// Creates the page.
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: BlocBuilder<EngineCubit, EngineState>(
        builder: (context, state) => switch (state) {
          EngineStarting() => const Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                CircularProgressIndicator(),
                SizedBox(height: 16),
                Text('Starting Synapse...'),
              ],
            ),
          ),
          EngineFailed(:final message) => Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(message),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: context.read<EngineCubit>().start,
                  child: const Text('Try again'),
                ),
              ],
            ),
          ),
          EngineReady(:final client) => _ReadyView(client: client),
        },
      ),
    );
  }
}

class _ReadyView extends StatelessWidget {
  const _ReadyView({required this.client});

  final EngineClient client;

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider(
          create: (_) => DocumentsBloc(client)..add(const DocumentsLoaded()),
        ),
        BlocProvider(create: (_) => ChatBloc(client)),
      ],
      child: const Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(width: 300, child: DocumentsPanel()),
          VerticalDivider(width: 1),
          Expanded(child: ChatPanel()),
        ],
      ),
    );
  }
}

/// The drop zone and the document list.
class DocumentsPanel extends StatelessWidget {
  /// Creates the panel.
  const DocumentsPanel({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<DocumentsBloc, DocumentsState>(
      builder: (context, state) => Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Your documents',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            DropTarget(
              onDragDone: (details) => context.read<DocumentsBloc>().add(
                DocumentsDropped([for (final f in details.files) f.path]),
              ),
              child: Container(
                height: 120,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  border: Border.all(
                    color: Theme.of(context).colorScheme.outline,
                  ),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text(
                  'Drop PDF files here',
                  textAlign: TextAlign.center,
                ),
              ),
            ),
            if (state.progress case final progress?) ...[
              const SizedBox(height: 12),
              const LinearProgressIndicator(),
              const SizedBox(height: 4),
              Text(progress),
            ],
            if (state.error case final error?) ...[
              const SizedBox(height: 12),
              Text(
                error,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
            const SizedBox(height: 12),
            Expanded(
              child: ListView(
                children: [
                  for (final document in state.documents)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(document.name),
                      subtitle: Text('${document.pages} pages'),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The questions, answers and sources.
class ChatPanel extends StatefulWidget {
  /// Creates the panel.
  const ChatPanel({super.key});

  @override
  State<ChatPanel> createState() => _ChatPanelState();
}

class _ChatPanelState extends State<ChatPanel> {
  final _input = TextEditingController();

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  void _send() {
    // While an answer is being written, the typed question stays in the box.
    final bloc = context.read<ChatBloc>();
    if (bloc.state.isAnswering) {
      return;
    }
    bloc.add(ChatQuestionAsked(_input.text));
    _input.clear();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          Expanded(
            child: BlocBuilder<ChatBloc, ChatState>(
              builder: (context, state) => state.exchanges.isEmpty
                  ? const Center(
                      child: Text(
                        'Add a document, then ask a question about it.',
                      ),
                    )
                  : ListView(
                      children: [
                        for (final exchange in state.exchanges)
                          _ExchangeView(exchange: exchange),
                      ],
                    ),
            ),
          ),
          TextField(
            controller: _input,
            onSubmitted: (_) => _send(),
            decoration: InputDecoration(
              hintText: 'Ask something...',
              border: const OutlineInputBorder(),
              suffixIcon: BlocBuilder<ChatBloc, ChatState>(
                buildWhen: (a, b) => a.isAnswering != b.isAnswering,
                builder: (context, state) => IconButton(
                  tooltip: 'Send',
                  icon: const Icon(Icons.send),
                  onPressed: state.isAnswering ? null : _send,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ExchangeView extends StatelessWidget {
  const _ExchangeView({required this.exchange});

  final ChatExchange exchange;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(exchange.question, style: theme.textTheme.titleSmall),
          const SizedBox(height: 8),
          SelectableText(exchange.answer),
          if (exchange.problem case final problem?)
            Text(problem, style: TextStyle(color: theme.colorScheme.error)),
          for (final citation in exchange.citations)
            _SourceView(citation: citation),
        ],
      ),
    );
  }
}

class _SourceView extends StatelessWidget {
  const _SourceView({required this.citation});

  final Citation citation;

  @override
  Widget build(BuildContext context) {
    final label = citation.isInferred
        ? 'Likely source: ${citation.documentName}, page ${citation.page}'
        : '[${citation.number}] ${citation.documentName}, '
              'page ${citation.page}';
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      title: Text(label, style: Theme.of(context).textTheme.bodySmall),
      children: [SelectableText(citation.text)],
    );
  }
}
