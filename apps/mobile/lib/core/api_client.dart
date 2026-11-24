import 'dart:math';

import 'package:dio/dio.dart';

import 'config.dart';
import 'failures.dart';

/// Единый HTTP-клиент: разбирает envelope `{success, data, error, trace_id}`.
class ApiClient {
  ApiClient({Dio? dio})
      : _dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: AppConfig.apiBaseUrl,
                connectTimeout: AppConfig.requestTimeout,
                receiveTimeout: AppConfig.requestTimeout,
                headers: const {'Accept': 'application/json'},
              ),
            ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          options.headers['X-Trace-Id'] =
              Random().nextInt(1 << 32).toRadixString(16).padLeft(8, '0');
          handler.next(options);
        },
      ),
    );
  }

  final Dio _dio;

  /// Выполнить GET и вернуть тело `data` как map.
  Future<Map<String, dynamic>> getJson(
    String path, {
    Map<String, dynamic>? query,
  }) async {
    final response = await _get(path, query);
    final data = response['data'];
    if (data is Map<String, dynamic>) return data;
    throw const ApiFailure('BAD_CONTRACT', 'Ожидался объект в ответе API');
  }

  /// Выполнить GET и вернуть `data` как список.
  Future<List<dynamic>> getList(
    String path, {
    Map<String, dynamic>? query,
  }) async {
    final response = await _get(path, query);
    final data = response['data'];
    if (data is List) return data;
    throw const ApiFailure('BAD_CONTRACT', 'Ожидался список в ответе API');
  }

  Future<Map<String, dynamic>> _get(
    String path,
    Map<String, dynamic>? query,
  ) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        path,
        queryParameters: query,
      );
      final body = response.data;
      if (body == null) {
        throw const ApiFailure('EMPTY_RESPONSE', 'Пустой ответ сервера');
      }
      if (body['success'] == false) {
        final error = body['error'] as Map<String, dynamic>? ?? {};
        throw ApiFailure(
          error['code']?.toString() ?? 'UNKNOWN',
          error['message']?.toString() ?? 'Ошибка запроса',
          body['trace_id']?.toString(),
        );
      }
      return body;
    } on DioException catch (e) {
      throw ApiFailure(
        'NETWORK_ERROR',
        e.message ?? 'Нет связи с API',
        null,
      );
    }
  }
}
