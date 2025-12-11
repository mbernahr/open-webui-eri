<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import Check from '$lib/components/icons/Check.svelte';
	import { flyAndScale } from '$lib/utils/transitions';
	import { getContext } from 'svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { t } from 'i18next';

	const i18n = getContext('i18n');

	export let id = '';
	export let value = '';
	export let placeholder = $i18n.t('Select Data');
	export let items: {
		label: string;
		value: string;
		description?: string;
		badge?: string;
		tags?: string[];
	}[] = [];

	export let className = 'w-[32rem]';
	export let triggerClassName = 'text-lg';

	export let tags: string[] = [];
	export let selectedTag = '';
	export let onSelectTag = (tag: string) => {};

	let show = false;
	let searchValue = '';

	$: filteredItems = searchValue
		? items.filter(
				(item) =>
					item.label.toLowerCase().includes(searchValue.trim().toLowerCase()) &&
					(selectedTag === '' || item.tags?.includes(selectedTag))
			)
		: items.filter((item) => selectedTag === '' || item.tags?.includes(selectedTag));

	async function selectedItem(item) {
		value = item.value;
		show = false;

		const isEri = 
			item.badge === 'ERI' ||
			(item.data && (item.data.data_source || '').toLowerCase() === 'eri');

		if (isEri) {
			try {
				await fetch(`/api/v1/knowledge/${item.value}/eri/ensure`, {
					method: 'POST',
					headers: {
						'Content-Type': 'application/json',
						Authorization: `Bearer ${localStorage.token}`
					}
				});
			} catch (err) {
				console.error('ERI ensure via dropdown failed', err);
			}
		}
	}
</script>

<DropdownMenu.Root bind:open={show}>
	<DropdownMenu.Trigger class="relative w-full font-primary" aria-label={placeholder} id="knowledge-selector-{id}-button">
		<div class="flex w-full text-left px-0.5 truncate bg-transparent {triggerClassName} justify-between font-medium placeholder-gray-400">
			{#if value}
				{items.find((item) => item.value === value)?.label ?? placeholder}
				<Tooltip content={$i18n.t('Remove')}>
					<button
						on:click={() => (value = '')}
						class="ml-2 size-4 flex items-center justify-center rounded-full hover:bg-gray-200 dark:hover:bg-gray-700"
						aria-label="Clear selection"
					>
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3">
							<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</Tooltip>
			{:else}
				{placeholder}
			{/if}
			<ChevronDown className="self-center ml-2 size-3" strokeWidth="2.5" />
		</div>
	</DropdownMenu.Trigger>

	<DropdownMenu.Content
		class="z-40 {className} max-w-[calc(100vw-1rem)] rounded-xl bg-white dark:bg-gray-850 dark:text-white shadow-lg"
		transition={flyAndScale}
		side="bottom-start"
		sideOffset={3}
	>
		<!-- Search -->
		<div class="flex items-center gap-2.5 px-5 pt-3 pb-2">
			<Search className="size-4" strokeWidth="2.5" />
			<input
				type="text"
				bind:value={searchValue}
				placeholder={$i18n.t('Search Data')}
				class="w-full px-0 py-1.5 text-sm bg-transparent outline-none"
			/>
		</div>

		<!-- Tags -->
		{#if tags.length > 0}
			<div class="flex gap-1 px-4 pt-3 pb-1 text-sm overflow-x-auto scrollbar-none">
				<button
					class="min-w-fit px-2 py-1 rounded-full transition font-medium
						{selectedTag === ''
							? 'text-black dark:text-white font-semibold'
							: 'text-gray-400 hover:text-black dark:hover:text-white'}"
					on:click={() => onSelectTag('')}
				>
					All
				</button>
				{#each tags as tag}
					<button
						class="min-w-fit px-2 py-1 rounded-full transition font-medium
							{selectedTag === tag
								? 'text-black dark:text-white font-semibold'
								: 'text-gray-400 hover:text-black dark:hover:text-white'}"
						on:click={() => onSelectTag(tag)}
					>
						{tag}
					</button>
				{/each}
			</div>
		{/if}

		<!-- Results -->
		<div class="px-2 pb-2 max-h-60 overflow-y-auto">
			{#each filteredItems as item}
				<button
					class="flex w-full text-left items-start gap-2 rounded-md py-2 px-3 text-sm hover:bg-gray-100 dark:hover:bg-gray-800"
					on:click={() => selectedItem(item)}
				>
					<img src="/static/favicon.png" alt="KB" class="rounded-full size-5 mt-1" />
					<div class="flex flex-col items-start w-full">
						<div class="flex items-center gap-2 w-full">
							<span class="font-medium">{item.label}</span>

							{#if item.badge}
								<span class="text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase
									{item.badge === 'ERI' ? 'bg-blue-100 text-blue-800' : ''}
									{item.badge === 'COLLECTION' ? 'bg-green-100 text-green-800' : ''}
									{item.badge === 'DOCUMENT' ? 'bg-yellow-100 text-yellow-800' : ''}"
								>
									{item.badge}
								</span>
							{/if}

							{#if value === item.value}
								<span class="ml-auto text-green-600">
									<Check className="size-4" />
								</span>
							{/if}
						</div>

						{#if item.description}
							<div class="text-xs text-gray-500 dark:text-gray-400 line-clamp-1">
								{item.description}
							</div>
						{/if}
					</div>
				</button>
			{:else}
				<div class="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
					{$i18n.t('No results found')}
				</div>
			{/each}
		</div>
	</DropdownMenu.Content>
</DropdownMenu.Root>
