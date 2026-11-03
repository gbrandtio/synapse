/// The outcome of an operation that can fail in an expected way.
sealed class Result<T> {
  const Result();
}

/// A successful outcome.
final class Success<T> extends Result<T> {
  /// Creates a success holding [value].
  const Success(this.value);

  /// The value produced.
  final T value;
}

/// A failed outcome, with a [message] that is safe to show the user.
final class Failure<T> extends Result<T> {
  /// Creates a failure.
  const Failure(this.message);

  /// A plain explanation for the user.
  final String message;
}
