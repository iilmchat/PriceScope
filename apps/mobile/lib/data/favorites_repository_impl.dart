import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../domain/entities.dart';
import '../domain/repositories.dart';

/// Избранное хранится локально как JSON-массив (офлайн-доступ).
class FavoritesRepositoryImpl implements FavoritesRepository {
  const FavoritesRepositoryImpl(this._prefs);

  static const String _key = 'pricescope.favorites.v1';

  final SharedPreferences _prefs;

  @override
  Future<List<Favorite>> load() async {
    final raw = _prefs.getString(_key);
    if (raw == null || raw.isEmpty) return const <Favorite>[];
    try {
      final decoded = jsonDecode(raw) as List<dynamic>;
      return decoded
          .whereType<Map<String, dynamic>>()
          .map(
            (item) => Favorite(
              externalId: item['external_id']?.toString() ?? '',
              storeCode: item['store_code']?.toString() ?? '',
              name: item['name']?.toString() ?? '',
              priceMinor: (item['price_minor'] as num?)?.toInt() ?? 0,
              imageUrl: item['image_url']?.toString(),
            ),
          )
          .where((favorite) => favorite.externalId.isNotEmpty)
          .toList();
    } on FormatException {
      return const <Favorite>[];
    }
  }

  @override
  Future<void> add(Favorite favorite) async {
    final items = await load();
    if (items.any((item) => item.externalId == favorite.externalId)) return;
    items.add(favorite);
    await _save(items);
  }

  @override
  Future<void> remove(String externalId) async {
    final items = await load();
    items.removeWhere((item) => item.externalId == externalId);
    await _save(items);
  }

  Future<void> _save(List<Favorite> items) async {
    final encoded = jsonEncode(
      items
          .map(
            (item) => {
              'external_id': item.externalId,
              'store_code': item.storeCode,
              'name': item.name,
              'price_minor': item.priceMinor,
              'image_url': item.imageUrl,
            },
          )
          .toList(),
    );
    await _prefs.setString(_key, encoded);
  }
}
