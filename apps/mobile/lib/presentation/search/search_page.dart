import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../domain/entities.dart';
import '../providers.dart';
import '../widgets/empty_state.dart';

/// Экран поиска товаров.
class SearchPage extends ConsumerWidget {
  const SearchPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final query = ref.watch(searchQueryProvider);
    final products = ref.watch(productsProvider(query));

    return Scaffold(
      appBar: AppBar(
        title: const Text('PriceScope — поиск'),
        actions: [
          IconButton(
            icon: const Icon(Icons.favorite_border),
            tooltip: 'Избранное',
            onPressed: () => context.go('/favorites'),
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Настройки',
            onPressed: () => context.go('/settings'),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              decoration: const InputDecoration(
                hintText: 'Название товара…',
                prefixIcon: Icon(Icons.search),
                border: OutlineInputBorder(),
              ),
              onChanged: (value) =>
                  ref.read(searchQueryProvider.notifier).state = value,
            ),
          ),
          Expanded(
            child: products.when(
              data: (items) => items.isEmpty
                  ? const EmptyState(
                      message: 'Введите название товара или запустите парсер '
                          'командой pricescope parse --store lenta',
                      icon: Icons.search_off,
                    )
                  : ListView.separated(
                      itemCount: items.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (context, index) =>
                          _ProductTile(product: items[index]),
                    ),
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => EmptyState(message: 'Ошибка: $error', icon: Icons.error_outline),
            ),
          ),
        ],
      ),
    );
  }
}

class _ProductTile extends ConsumerWidget {
  const _ProductTile({required this.product});

  final Product product;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ListTile(
      leading: product.imageUrl == null
          ? const Icon(Icons.shopping_bag_outlined)
          : Image.network(
              product.imageUrl!,
              width: 48,
              height: 48,
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) => const Icon(Icons.broken_image_outlined),
            ),
      title: Text(product.name, maxLines: 2),
      subtitle: Text(product.brand ?? product.category ?? ''),
      trailing: IconButton(
        icon: const Icon(Icons.favorite_border),
        tooltip: 'В избранное',
        onPressed: () async {
          final manager = await ref.read(manageFavoritesProvider.future);
          await manager.add(
            Favorite(
              externalId: product.id.toString(),
              storeCode: 'lenta',
              name: product.name,
              priceMinor: 0,
              imageUrl: product.imageUrl,
            ),
          );
          ref.invalidate(favoritesProvider);
        },
      ),
      onTap: () => context.go('/product/${product.id}'),
    );
  }
}
