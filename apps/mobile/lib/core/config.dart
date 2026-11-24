/// Глобальная конфигурация клиента (только --dart-define, без хардкода).
class AppConfig {
  const AppConfig._();

  /// Адрес API. Для телефона в той же сети укажите IP компьютера.
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8765',
  );

  static const Duration requestTimeout = Duration(seconds: 20);

  /// Версия продукта, совпадает с pyproject.toml.
  static const String version = '0.1.0';
}
