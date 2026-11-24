/// Глобальная конфигурация клиента (только --dart-define, без хардкода).
class AppConfig {
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8765',
  );

  static const Duration requestTimeout = Duration(seconds: 20);

  static void init() {
    // Зарезервировано под инициализацию drift/логирования (S08).
  }
}
