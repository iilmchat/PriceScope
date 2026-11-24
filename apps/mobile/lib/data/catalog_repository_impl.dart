import '../core/api_client.dart';
import '../domain/entities.dart';
import '../domain/repositories.dart';
import 'api_dto.dart';

/// Реализация порта каталога поверх REST API.
class CatalogRepositoryImpl implements CatalogRepository {
  const CatalogRepositoryImpl(this._api);

  final ApiClient _api;

  @override
  Future<List<Product>> search(String query) async {
    final page = await _api.getJson(
      '/api/v1/products',
      query: {'query': query, 'page': 1, 'page_size': 50},
    );
    final items = (page['items'] as List?) ?? const <dynamic>[];
    return items
        .whereType<Map<String, dynamic>>()
        .map(parseProduct)
        .toList();
  }

  @override
  Future<Product?> product(int id) async {
    try {
      final json = await _api.getJson('/api/v1/products/$id');
      return parseProduct(json);
    } on ApiFailure {
      return null;
    }
  }

  @override
  Future<List<PricePoint>> history({
    int? productId,
    String? externalId,
    String? storeCode,
  }) async {
    final query = <String, dynamic>{'page': 1, 'page_size': 100};
    if (productId != null) query['product_id'] = productId;
    if (externalId != null) query['external_id'] = externalId;
    if (storeCode != null && storeCode.isNotEmpty) {
      query['store_code'] = storeCode;
    }
    final page = await _api.getJson('/api/v1/observations', query: query);
    final items = (page['items'] as List?) ?? const <dynamic>[];
    final points = items
        .whereType<Map<String, dynamic>>()
        .map(parsePricePoint)
        .toList();
    points.sort((a, b) => a.observedAt.compareTo(b.observedAt));
    return points;
  }

  @override
  Future<List<PriceComparison>> compare({
    int? productId,
    String? query,
    required double lat,
    required double lon,
  }) async {
    if (productId == null && (query == null || query.isEmpty)) {
      return const <PriceComparison>[];
    }
    final params = <String, dynamic>{'lat': lat, 'lon': lon};
    if (productId != null) params['product_id'] = productId;
    if (query != null) params['query'] = query;
    final rows = await _api.getList('/api/v1/compare', query: params);
    return rows
        .whereType<Map<String, dynamic>>()
        .map(parseComparison)
        .toList();
  }
}
