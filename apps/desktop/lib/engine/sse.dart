import 'dart:convert';

/// One server-sent event.
final class SseEvent {
  /// Creates an event.
  const SseEvent(this.name, this.data);

  /// The event's name.
  final String name;

  /// The decoded JSON object.
  final Map<String, Object?> data;
}

/// Turns a byte stream into events.
///
/// Comments and events without a name, such as keep-alive pings, are skipped.
Stream<SseEvent> parseSse(Stream<List<int>> bytes) async* {
  String? name;
  final data = StringBuffer();
  final lines = bytes.transform(utf8.decoder).transform(const LineSplitter());
  await for (final line in lines) {
    if (line.isEmpty) {
      if (name != null && data.isNotEmpty) {
        yield SseEvent(
          name,
          jsonDecode(data.toString()) as Map<String, Object?>,
        );
      }
      name = null;
      data.clear();
    } else if (line.startsWith('event:')) {
      name = line.substring(6).trim();
    } else if (line.startsWith('data:')) {
      data.write(line.substring(5).trim());
    }
  }
}
