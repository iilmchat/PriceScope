import 'entities.dart';

/// Порт каталога/цен (реализуется поверх REST API).
abstract class CatalogRepository {
  Future<List<Product>> search(String query);
  Future<Product?> product(int id);
  Future<List<PricePoint>> history({int? productId, String? externalId, String? storeCode});
  Future<List<PriceComparison>> compare({
    int? productId,
    String? query,
    required double lat,
    required double lon,
  });
}

/// Порт локального хранилища избранного.
abstract class FavoritesRepository {
  Future<List<Favorite>> load();
  Future<void> add(Favorite favorite);
  Future<void> remove(String externalId);
}
