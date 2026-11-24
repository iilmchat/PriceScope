import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers.dart';
import '../widgets/empty_state.dart';
import '../widgets/price_badge.dart';

/// Экран сравнения цен по магазинам.
class ComparePage extends ConsumerStatefulWidget {
  const ComparePage({super.key, required this.initialQuery});

  final String initialQuery;

  @override
  ConsumerState<ComparePage> createState() => _ComparePageState();
}

class _ComparePageState extends ConsumerState<ComparePage> {
  late final TextEditingController _controller;
  String _query = '';

  @override
  void initState() {
    super.initState();
    _query = widget.initialQuery;
    _controller = TextEditingController(text: _query);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final rows = ref.watch(compareResultsProvider(_query));

    return Scaffold(
      appBar: AppBar(title: const Text('Сравнение цен')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    decoration: const InputDecoration(
                      hintText: 'Название товара…',
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (value) => setState(() => _query = value),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: () => setState(() => _query = _controller.text),
                  child: const Text('Найти'),
                ),
              ],
            ),
          ),
          Expanded(
            child: rows.when(
              data: (items) => items.isEmpty
                  ? const EmptyState(
                      message: 'Нет данных. Укажите название и запустите парсеры магазинов.',
                      icon: Icons.compare_arrows,
                    )
                  : ListView.builder(
                      itemCount: items.length,
                      itemBuilder: (context, index) {
                        final row = items[index];
                        return ListTile(
                          leading: Icon(
                            row.isCheapest ? Icons.local_offer : Icons.store,
                            color: row.isCheapest ? Colors.green : null,
                          ),
                          title: Text(row.storeCode),
                          subtitle: Text(
                            '${row.observedAt.toLocal()}'
                            '${row.savingsPct > 0 ? ' · +${row.savingsPct.toStringAsFixed(1)} %' : ''}',
                          ),
                          trailing: PriceBadge(
                            priceMinor: row.priceMinor,
                            isCheapest: row.isCheapest,
                          ),
                        );
                      },
                    ),
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => EmptyState(message: 'Ошибка: $error'),
            ),
          ),
        ],
      ),
    );
  }
}
