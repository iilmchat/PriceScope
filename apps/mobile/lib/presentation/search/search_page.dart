import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers.dart';

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
            icon: const Icon(Icons.settings_outlined),
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
              onChanged: (value) => ref.read(searchQueryProvider.notifier).state = value,
            ),
          ),
          Expanded(
            child: products.when(
              data: (items) => ListView.builder(
                itemCount: items.length,
                itemBuilder: (context, index) {
                  final item = items[index];
                  return ListTile(
                    leading: item.imageUrls.isEmpty
                        ? const Icon(Icons.shopping_bag_outlined)
                        : Image.network(item.imageUrls.first, width: 48, height: 48, fit: BoxFit.cover),
                    title: Text(item.name),
                    subtitle: Text(item.brand ?? ''),
                    onTap: () => context.go('/compare/${item.id}'),
                  );
                },
              ),
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => Center(child: Text('Ошибка: $error')),
            ),
          ),
        ],
      ),
    );
  }
}
