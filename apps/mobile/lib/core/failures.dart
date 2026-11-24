/// Пользовательская ошибка API с кодом и trace_id.
class ApiFailure implements Exception {
  const ApiFailure(this.code, this.message, this.traceId);

  final String code;
  final String message;
  final String? traceId;

  @override
  String toString() => '$code: $message${traceId != null ? ' (trace: $traceId)' : ''}';
}
