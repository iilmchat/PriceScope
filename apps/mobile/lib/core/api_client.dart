import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'config.dart';
import 'failures.dart';

/// Единый HTTP-клиент с разбором generalного формата ошибок API.
final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

class ApiClient {
  ApiClient()
      : _dio = Dio(BaseOptions(
          baseUrl: AppConfig.apiBaseUrl,
          connectTimeout: AppConfig.requestTimeout,
          receiveTimeout: AppConfig.requestTimeout,
        ));

  final Dio _dio;

  Future<Map<String, dynamic>> getJson(
    String path, {
    Map<String, dynamic>? query,
  }) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(path, queryParameters: query);
      final body = response.data ?? {};
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
      throw ApiFailure('NETWORK_ERROR', e.message ?? 'Нет связи с API', null);
    }
  }
}
