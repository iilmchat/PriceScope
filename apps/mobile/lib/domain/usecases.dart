import 'entities.dart';
import 'repositories.dart';

/// Поиск товаров по названию.
class SearchProducts {
  const SearchProducts(this._catalog);

  final CatalogRepository _catalog;

  Future<List<Product>> call(String query) => _catalog.search(query);
}

/// Карточка товара по id.
class GetProductDetails {
  const GetProductDetails(this._catalog);

  final CatalogRepository _catalog;

  Future<Product?> call(int id) => _catalog.product(id);
}

/// История цен товара (для графика).
class GetPriceHistory {
  const GetPriceHistory(this._catalog);

  final CatalogRepository _catalog;

  Future<List<PricePoint>> call(int productId, {String? storeCode}) =>
      _catalog.history(productId: productId, storeCode: storeCode);
}

/// Сравнение цен в магазинах рядом с точкой.
class ComparePrices {
  const ComparePrices(this._catalog);

  final CatalogRepository _catalog;

  Future<List<PriceComparison>> call(String query, {double lat = 55.3925, double lon = 36.7323}) =>
      _catalog.compare(query: query, lat: lat, lon: lon);
}

/// Управление избранным (локальное хранилище).
class ManageFavorites {
  const ManageFavorites(this._favorites);

  final FavoritesRepository _favorites;

  Future<List<Favorite>> load() => _favorites.load();
  Future<void> add(Favorite favorite) => _favorites.add(favorite);
  Future<void> remove(String externalId) => _favorites.remove(externalId);
}
