import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers.dart';
import '../widgets/empty_state.dart';

/// Экран избранного (локальное хранилище).
class FavoritesPage extends ConsumerWidget {
  const FavoritesPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final favorites = ref.watch(favoritesProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Избранное')),
      body: favorites.when(
        data: (items) => items.isEmpty
            ? const EmptyState(
                message: 'Нажмите ♡ у товара, чтобы добавить его в избранное',
                icon: Icons.favorite_border,
              )
            : ListView.builder(
                itemCount: items.length,
                itemBuilder: (context, index) {
                  final item = items[index];
                  return ListTile(
                    leading: const Icon(Icons.favorite, color: Colors.pink),
                    title: Text(item.name),
                    subtitle: Text('${item.storeCode} · ${item.externalId}'),
                    trailing: IconButton(
                      icon: const Icon(Icons.delete_outline),
                      tooltip: 'Удалить',
                      onPressed: () async {
                        final manager = await ref.read(manageFavoritesProvider.future);
                        await manager.remove(item.externalId);
                        ref.invalidate(favoritesProvider);
                      },
                    ),
                  );
                },
              ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => EmptyState(message: 'Ошибка: $error'),
      ),
    );
  }
}
