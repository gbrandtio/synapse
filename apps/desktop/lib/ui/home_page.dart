import 'package:desktop_drop/desktop_drop.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../chat/chat_bloc.dart';
import '../documents/documents_bloc.dart';
import '../engine/engine_client.dart';
import '../engine/engine_cubit.dart';
import '../engine/models.dart';
import 'theme.dart';

const _chatWidth = 720.0;

/// Shows start-up status, then the main screen.
class HomePage extends StatelessWidget {
  /// Creates the page.
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: BlocBuilder<EngineCubit, EngineState>(
        builder: (context, state) => switch (state) {
          EngineStarting() => const _CentredStatus(
            top: SizedBox.square(
              dimension: 20,
              child: CircularProgressIndicator(),
            ),
            child: Text('Starting Synapse...'),
          ),
          EngineFailed(:final message) => _CentredStatus(
            bottom: FilledButton(
              onPressed: context.read<EngineCubit>().start,
              child: const Text('Try again'),
            ),
            child: Text(message, textAlign: TextAlign.center),
          ),
          // The key gives a restarted engine new blocs, with the new client.
          EngineReady(:final client, :final restarted) => _ReadyView(
            key: ValueKey(client),
            client: client,
            restarted: restarted,
          ),
        },
      ),
    );
  }
}

class _CentredStatus extends StatelessWidget {
  const _CentredStatus({required this.child, this.top, this.bottom});

  final Widget child;
  final Widget? top;
  final Widget? bottom;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (top case final top?) ...[top, const SizedBox(height: 20)],
          child,
          if (bottom case final bottom?) ...[
            const SizedBox(height: 20),
            bottom,
          ],
        ],
      ),
    );
  }
}

class _ReadyView extends StatelessWidget {
  const _ReadyView({required this.client, required this.restarted, super.key});

  final EngineClient client;
  final bool restarted;

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider(
          create: (_) => DocumentsBloc(client)..add(const DocumentsLoaded()),
        ),
        BlocProvider(create: (_) => ChatBloc(client)),
      ],
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(width: 288, child: DocumentsPanel()),
          const VerticalDivider(width: 1),
          Expanded(child: ChatPanel(restarted: restarted)),
        ],
      ),
    );
  }
}

/// The app's name, the drop zone and the document list.
class DocumentsPanel extends StatelessWidget {
  /// Creates the panel.
  const DocumentsPanel({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return BlocBuilder<DocumentsBloc, DocumentsState>(
      builder: (context, state) => Padding(
        padding: const EdgeInsets.fromLTRB(24, 28, 24, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Synapse', style: theme.textTheme.titleMedium),
            const SizedBox(height: 28),
            const _DropZone(),
            if (state.progress case final progress?) ...[
              const SizedBox(height: 16),
              const LinearProgressIndicator(),
              const SizedBox(height: 6),
              Text(
                progress,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall,
              ),
            ],
            if (state.error case final error?) ...[
              const SizedBox(height: 16),
              Text(
                error,
                maxLines: 6,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.error,
                ),
              ),
            ],
            const SizedBox(height: 28),
            Text('Your documents', style: theme.textTheme.labelSmall),
            const SizedBox(height: 8),
            Expanded(
              child: ListView(
                children: [
                  for (final document in state.documents)
                    _DocumentRow(document: document),
                ],
              ),
            ),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                onPressed: () => showDialog<void>(
                  context: context,
                  builder: (_) => const TermsDialog(),
                ),
                child: const Text('Terms and licences'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DropZone extends StatefulWidget {
  const _DropZone();

  @override
  State<_DropZone> createState() => _DropZoneState();
}

class _DropZoneState extends State<_DropZone> {
  bool _isOver = false;

  @override
  Widget build(BuildContext context) {
    return DropTarget(
      onDragEntered: (_) => setState(() => _isOver = true),
      onDragExited: (_) => setState(() => _isOver = false),
      onDragDone: (details) => context.read<DocumentsBloc>().add(
        DocumentsDropped([for (final f in details.files) f.path]),
      ),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        height: 112,
        decoration: BoxDecoration(
          color: _isOver ? SynapseColors.wash : Colors.white,
          border: Border.all(
            color: _isOver ? SynapseColors.ink : SynapseColors.line,
          ),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.add, size: 20, color: SynapseColors.muted),
            const SizedBox(height: 6),
            Text(
              'Drop PDF files here',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _DocumentRow extends StatelessWidget {
  const _DocumentRow({required this.document});

  final DocumentInfo document;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            document.name,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.titleSmall?.copyWith(fontSize: 13),
          ),
          Text('${document.pages} pages', style: theme.textTheme.bodySmall),
        ],
      ),
    );
  }
}

/// Shows the terms of use, read from the app's own files.
class TermsDialog extends StatelessWidget {
  /// Creates the dialog.
  const TermsDialog({super.key});

  @override
  Widget build(BuildContext context) {
    return Dialog(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 640, maxHeight: 640),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(32, 28, 16, 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Terms and licences',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 16),
              Expanded(
                child: FutureBuilder<String>(
                  future: rootBundle.loadString('assets/legal/TERMS.txt'),
                  builder: (context, snapshot) => SingleChildScrollView(
                    child: Padding(
                      padding: const EdgeInsets.only(right: 16),
                      child: SelectableText(
                        snapshot.data ?? '',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: SynapseColors.ink,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Close'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The questions, answers and sources.
class ChatPanel extends StatefulWidget {
  /// Creates the panel. [restarted] shows that the engine had to restart.
  const ChatPanel({this.restarted = false, super.key});

  /// Whether to tell the user the engine restarted.
  final bool restarted;

  @override
  State<ChatPanel> createState() => _ChatPanelState();
}

class _ChatPanelState extends State<ChatPanel> {
  final _input = TextEditingController();
  late bool _showRestart = widget.restarted;

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
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: _chatWidth),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(32, 28, 32, 28),
          child: Column(
            children: [
              if (_showRestart)
                _RestartNotice(
                  onClose: () => setState(() => _showRestart = false),
                ),
              Expanded(
                child: BlocBuilder<ChatBloc, ChatState>(
                  builder: (context, state) => state.exchanges.isEmpty
                      ? const _EmptyChat()
                      : ListView(
                          children: [
                            for (final exchange in state.exchanges)
                              _ExchangeView(exchange: exchange),
                          ],
                        ),
                ),
              ),
              const SizedBox(height: 16),
              _QuestionBox(controller: _input, onSend: _send),
            ],
          ),
        ),
      ),
    );
  }
}

class _RestartNotice extends StatelessWidget {
  const _RestartNotice({required this.onClose});

  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        children: [
          Expanded(
            child: Text(
              'Synapse had a problem and restarted. Documents you already '
              'added are safe, but this conversation was cleared.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          IconButton(
            tooltip: 'Dismiss',
            iconSize: 16,
            color: SynapseColors.muted,
            icon: const Icon(Icons.close),
            onPressed: onClose,
          ),
        ],
      ),
    );
  }
}

class _EmptyChat extends StatelessWidget {
  const _EmptyChat();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('Ask your documents', style: theme.textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text(
            'Add a document, then ask a question about it.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: SynapseColors.muted,
            ),
          ),
        ],
      ),
    );
  }
}

class _QuestionBox extends StatelessWidget {
  const _QuestionBox({required this.controller, required this.onSend});

  final TextEditingController controller;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    final border = OutlineInputBorder(
      borderRadius: BorderRadius.circular(26),
      borderSide: const BorderSide(color: SynapseColors.line),
    );
    return TextField(
      controller: controller,
      onSubmitted: (_) => onSend(),
      style: Theme.of(context).textTheme.bodyMedium,
      decoration: InputDecoration(
        hintText: 'Ask something...',
        hintStyle: Theme.of(
          context,
        ).textTheme.bodyMedium?.copyWith(color: SynapseColors.muted),
        contentPadding: const EdgeInsets.fromLTRB(22, 16, 8, 16),
        border: border,
        enabledBorder: border,
        focusedBorder: border.copyWith(
          borderSide: const BorderSide(color: SynapseColors.ink),
        ),
        suffixIconConstraints: const BoxConstraints.tightFor(
          width: 52,
          height: 36,
        ),
        suffixIcon: Padding(
          padding: const EdgeInsets.only(right: 16),
          child: BlocBuilder<ChatBloc, ChatState>(
            buildWhen: (a, b) => a.isAnswering != b.isAnswering,
            builder: (context, state) => IconButton(
              tooltip: 'Send',
              padding: EdgeInsets.zero,
              style: IconButton.styleFrom(
                backgroundColor: SynapseColors.ink,
                foregroundColor: Colors.white,
                disabledBackgroundColor: SynapseColors.line,
                disabledForegroundColor: Colors.white,
                iconSize: 18,
              ),
              icon: const Icon(Icons.arrow_upward),
              onPressed: state.isAnswering ? null : onSend,
            ),
          ),
        ),
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
      padding: const EdgeInsets.only(bottom: 32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(exchange.question, style: theme.textTheme.titleSmall),
          const SizedBox(height: 8),
          SelectableText(exchange.answer, style: theme.textTheme.bodyMedium),
          if (exchange.problem case final problem?)
            Text(
              problem,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.error,
              ),
            ),
          if (exchange.citations.isNotEmpty) const SizedBox(height: 8),
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
    final style = Theme.of(context).textTheme.bodySmall;
    final label = citation.isInferred
        ? 'Likely source: ${citation.documentName}, page ${citation.page}'
        : '[${citation.number}] ${citation.documentName}, '
              'page ${citation.page}';
    return ExpansionTile(
      dense: true,
      minTileHeight: 32,
      visualDensity: VisualDensity.compact,
      title: Text(label, style: style),
      children: [SelectableText(citation.text, style: style)],
    );
  }
}
