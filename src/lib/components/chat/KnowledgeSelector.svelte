<script lang="ts">
	import { getContext } from 'svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import Selector from './KnowledgeSelector/Selector.svelte';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	export let selectedKnowledges = [''];
	export let disabled = false;

	const i18n = getContext('i18n');

	let knowledgeItems = [];
	let knowledgeTags: string[] = [];
	let selectedTag = '';

	onMount(async () => {
		try {
			const res = await fetch('/api/v1/knowledge/list');
			if (!res.ok) throw new Error(`Fehler: ${res.status}`);
			const data = await res.json();

			knowledgeItems = data.map((kb) => {
				const badge = kb.meta?.document
					? 'DOCUMENT'
					: kb.data?.data_source === 'eri'
					? 'ERI'
					: 'COLLECTION';

				return {
					value: kb.id,
					label: kb.name,
					description: kb.description ?? '',
					badge,
					tags: [badge]
				};
			});

			const tagSet = new Set<string>();
			knowledgeItems.forEach((kb) => kb.tags?.forEach((tag) => tagSet.add(tag)));
			knowledgeTags = Array.from(tagSet).sort((a, b) => a.localeCompare(b));
		} catch (err) {
			console.error(err);
			toast.error($i18n.t('Failed to load knowledge bases'));
		}
	});
</script>

<div class="flex flex-col w-full items-start">
	{#each selectedKnowledges as selectedKnowledge, idx (idx)}
		<div class="flex items-center space-x-1">
			<div class="w-auto">
				<Selector
					id={`knowledge-${idx}`}
					placeholder={$i18n.t('Select Data')}
					items={knowledgeItems}
					tags={knowledgeTags}
					selectedTag={selectedTag}
					onSelectTag={(tag) => (selectedTag = tag)}
					bind:value={selectedKnowledges[idx]}
				/>
			</div>

			{#if idx === 0}
				<div class="self-center mx-1 -translate-y-[0.5px]">
					<Tooltip content={$i18n.t('Add Data')}>
						<button
							{disabled}
							on:click={() => {
								selectedKnowledges = [...selectedKnowledges, ''];
							}}
							aria-label="Add Data"
						>
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5">
								<path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m6-6H6" />
							</svg>
						</button>
					</Tooltip>
				</div>
			{:else}
				<div class="self-center mx-1 -translate-y-[0.5px]">
					<Tooltip content={$i18n.t('Remove Data')}>
						<button
							{disabled}
							on:click={() => {
								selectedKnowledges.splice(idx, 1);
								selectedKnowledges = [...selectedKnowledges];
							}}
							aria-label="Remove Data"
						>
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3">
								<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 12h-15" />
							</svg>
						</button>
					</Tooltip>
				</div>
			{/if}
		</div>
	{/each}
</div>
