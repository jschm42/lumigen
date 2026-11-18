<script setup lang="ts" generic="Row extends Record<string, any>">
import Card from './Card.vue'
import EmptyState from './EmptyState.vue'
import LoadingState from './LoadingState.vue'

/**
 * Tabular data in a panel. Customize a column via the `#cell-<key>` slot
 * (receives `{ row, value }`); the `#empty` slot replaces the default empty state.
 */
export interface DataTableColumn {
  key: string
  label: string
  align?: 'left' | 'right' | 'center'
  /** Extra classes for header and cells of this column (e.g. width, hiding on mobile). */
  class?: string
}

interface Props {
  columns: DataTableColumn[]
  rows: Row[]
  rowKey: keyof Row | ((row: Row) => string | number)
  loading?: boolean
  emptyTitle?: string
  emptyDescription?: string
  /** Accessible table caption (visually hidden). */
  caption?: string
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  emptyTitle: 'Nothing here yet',
})

function keyOf(row: Row): string | number {
  return typeof props.rowKey === 'function' ? props.rowKey(row) : (row[props.rowKey] as string | number)
}

const alignClasses = { left: 'text-left', right: 'text-right', center: 'text-center' } as const
</script>

<template>
  <Card padding="none" class="overflow-hidden">
    <LoadingState v-if="loading && rows.length === 0" size="sm" />
    <div v-else-if="rows.length === 0">
      <slot name="empty">
        <EmptyState :title="emptyTitle" :description="emptyDescription" size="sm" />
      </slot>
    </div>
    <div v-else class="overflow-x-auto">
      <table class="w-full border-collapse text-left text-xs">
        <caption v-if="caption" class="sr-only">{{ caption }}</caption>
        <thead>
          <tr
            class="border-b border-slate-200 bg-slate-50/50 text-2xs font-semibold uppercase tracking-wider text-slate-500 dark:border-white/10 dark:bg-slate-950/40 dark:text-slate-400"
          >
            <th
              v-for="column in columns"
              :key="column.key"
              scope="col"
              :class="['p-3.5', alignClasses[column.align ?? 'left'], column.class]"
            >
              {{ column.label }}
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-200/60 dark:divide-white/10">
          <tr v-for="row in rows" :key="keyOf(row)" class="transition-colors hover:bg-slate-50/50 dark:hover:bg-white/5">
            <td
              v-for="column in columns"
              :key="column.key"
              :class="['p-3.5 text-slate-700 dark:text-slate-300', alignClasses[column.align ?? 'left'], column.class]"
            >
              <!-- Fallback only when no cell slot exists: a slot that renders nothing (v-if) must stay empty. -->
              <slot v-if="$slots[`cell-${column.key}`]" :name="`cell-${column.key}`" :row="row" :value="row[column.key]" />
              <template v-else>{{ row[column.key] }}</template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </Card>
</template>
