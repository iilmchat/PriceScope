import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../data/models/product.dart';

/// Экран сравнения цен по магазинам.
class ComparePage extends ConsumerWidget {
  const ComparePage({required this.productId, super.key});

  final int productId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final future = ref.read(apiClientProvider).getJson(
          '/api/v1/compare',
          query: {'product_id': productId},
        );

    return Scaffold(
      appBar: AppBar(title: Text('Сравнение #$productId')),
      body: FutureBuilder<Map<String, dynamic>>(
        future: future,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return Center(child: Text('Ошибка: ${snapshot.error}'));
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final rows = (snapshot.data!['data'] as List? ?? const [])
              .whereType<Map<String, dynamic>>()
              .map(CompareRowDto.fromJson)
              .toList();
          if (rows.isEmpty) {
            return const Center(child: Text('Нет данных для сравнения'));
          }
          return ListView.builder(
            itemCount: rows.length,
            itemBuilder: (context, index) {
              final row = rows[index];
              return ListTile(
                leading: Icon(row.isCheapest ? Icons.local_offer : Icons.store),
                title: Text(row.storeCode),
                subtitle: Text(row.observedAt),
                trailing: Text('${(row.priceMinor / 100).toStringAsFixed(2)} ₽'),
              );
            },
          );
        },
      ),
    );
  }
}
