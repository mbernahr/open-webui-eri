<script lang="ts">
	import { getContext } from 'svelte';
	import { embed, showControls, showEmbeds } from '$lib/stores';
	import { getSourceUrl } from '$lib/utils/sources';

	import CitationModal from './Citations/CitationModal.svelte';
	import CitationsModal from './Citations/CitationsModal.svelte';

	const i18n = getContext('i18n');

	export let id = '';
	export let chatId = '';

	export let sources = [];
	export let readOnly = false;

	let citations = [];
	let showPercentage = false;
	let showRelevance = true;

	let showCitationsModal = false;
	let showCitationModal = false;

	let selectedCitation: any = null;

	const HTTP_URL_RE = /^https?:\/\//i;

	export const showSourceModal = (sourceId) => {
		let index;
		let suffix = null;

		if (typeof sourceId === 'string') {
			const output = sourceId.split('#');
			index = parseInt(output[0]) - 1;

			if (output.length > 1) {
				suffix = output[1];
			}
		} else {
			index = sourceId - 1;
		}

		if (citations[index]) {
			if (citations[index]?.source?.embed_url) {
				const embedUrl = citations[index].source.embed_url;
				if (embedUrl) {
					if (readOnly) {
						// Open in new tab if readOnly
						window.open(embedUrl, '_blank');
						return;
					} else {
						showControls.set(true);
						showEmbeds.set(true);
						embed.set({
							url: embedUrl,
							title: citations[index]?.source?.name || 'Embedded Content',
							source: citations[index],
							chatId: chatId,
							messageId: id,
							sourceId: sourceId
						});
					}
				} else {
					selectedCitation = citations[index];
					showCitationModal = true;
				}
			} else {
				selectedCitation = citations[index];
				showCitationModal = true;
			}
		}
	};

	function calculateShowRelevance(sources: any[]) {
		const distances = sources.flatMap((citation) => citation.distances ?? []);
		const inRange = distances.filter((d) => d !== undefined && d >= -1 && d <= 1).length;
		const outOfRange = distances.filter((d) => d !== undefined && (d < -1 || d > 1)).length;

		if (distances.length === 0) {
			return false;
		}

		if (
			(inRange === distances.length - 1 && outOfRange === 1) ||
			(outOfRange === distances.length - 1 && inRange === 1)
		) {
			return false;
		}

		return true;
	}

	function shouldShowPercentage(sources: any[]) {
		const distances = sources.flatMap((citation) => citation.distances ?? []);
		return distances.every((d) => d !== undefined && d >= -1 && d <= 1);
	}

	const getNonEmptySourceValue = (...values: unknown[]): string | null => {
		const placeholders = new Set(['', 'n/a', 'na', 'none', 'null', 'unknown']);
		for (const value of values) {
			if (value === null || value === undefined) continue;
			const normalized =
				typeof value === 'string' ? value.trim() : String(value).trim();
			if (normalized.length > 0 && !placeholders.has(normalized.toLowerCase())) {
				return normalized;
			}
		}
		return null;
	};

	const hashDocument = (document: string): string => {
		let hash = 0;
		for (let i = 0; i < document.length; i++) {
			hash = (hash << 5) - hash + document.charCodeAt(i);
			hash |= 0;
		}
		return Math.abs(hash).toString(36);
	};

	const getCitationIdentity = (
		metadata: Record<string, unknown> | undefined,
		source: Record<string, unknown> | undefined,
		document: unknown,
		fallbackIndex: number
	): string => {
		const sourceLinks = Array.isArray(source?.links) ? source.links : [];
		const key =
			getNonEmptySourceValue(
				metadata?.source,
				metadata?.path,
				metadata?.url,
				metadata?.filename,
				metadata?.name,
				metadata?.file_id,
				metadata?.id
			) ??
			getNonEmptySourceValue(
				sourceLinks[0],
				source?.path,
				source?.url,
				source?.id,
				source?.filename,
				source?.name
			);

		if (key) {
			return key;
		}

		if (typeof document === 'string' && document.trim().length > 0) {
			return `doc:${hashDocument(document.trim())}`;
		}

		return `source:${fallbackIndex}`;
	};

	$: {
		let fallbackIndex = 0;
		citations = sources.reduce((acc, source) => {
			if (Object.keys(source).length === 0) {
				return acc;
			}

			source?.document?.forEach((document, index) => {
				const metadata = source?.metadata?.[index];
				const distance = source?.distances?.[index];

				// Within the same citation there could be multiple documents
				const id = getCitationIdentity(metadata, source?.source, document, fallbackIndex);
				let _source = source?.source;

				if (metadata?.name) {
					_source = { ..._source, name: metadata.name };
				}

				const metadataLinks = Array.isArray(metadata?.links)
					? metadata.links.filter((link: unknown) => typeof link === 'string')
					: [];
				if (metadataLinks.length > 0) {
					_source = { ..._source, links: _source?.links ?? metadataLinks };
				}

				const metadataUrl = getNonEmptySourceValue(metadata?.source, metadata?.path, metadata?.url);
				if (metadataUrl && HTTP_URL_RE.test(metadataUrl)) {
					_source = {
						..._source,
						path: _source?.path ?? metadata?.path ?? metadata?.source,
						url: _source?.url ?? metadataUrl
					};
				}

				if (HTTP_URL_RE.test(id)) {
					_source = { ..._source, name: _source?.name ?? id, url: _source?.url ?? id };
				}
				const sourceUrl = getSourceUrl(_source);

				const existingSource = acc.find((item) => item.id === id);

				if (existingSource) {
					existingSource.document.push(document);
					existingSource.metadata.push(metadata);
					if (distance !== undefined) existingSource.distances.push(distance);
					if (!existingSource.sourceUrl && sourceUrl) {
						existingSource.sourceUrl = sourceUrl;
					}
				} else {
					acc.push({
						id: id,
						source: _source,
						sourceUrl,
						document: [document],
						metadata: metadata ? [metadata] : [],
						distances: distance !== undefined ? [distance] : []
					});
				}
				fallbackIndex += 1;
			});

			return acc;
		}, []);
			showRelevance = calculateShowRelevance(citations);
			showPercentage = shouldShowPercentage(citations);
		}

	const getSourceDomain = (url: string | null): string | null => {
		if (!url) return null;

		try {
			return new URL(url).hostname;
		} catch {
			return null;
		}
	};
</script>

	<CitationModal
		bind:show={showCitationModal}
		citation={selectedCitation}
		{showPercentage}
		{showRelevance}
	/>
	<CitationsModal
		id={id}
		bind:show={showCitationsModal}
		{citations}
		{showPercentage}
		{showRelevance}
	/>

{#if citations.length > 0}
	{@const urlCitations = citations.filter((c) => c?.sourceUrl)}
	<div class=" py-1 -mx-0.5 w-full flex gap-1 items-center flex-wrap">
			<button
				class="text-xs font-medium text-gray-600 dark:text-gray-300 px-3.5 h-8 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition flex items-center gap-1 border border-gray-50 dark:border-gray-850/30"
				on:click={() => {
					showCitationsModal = true;
				}}
			>
			{#if urlCitations.length > 0}
				<div class="flex -space-x-1 items-center">
					{#each urlCitations.slice(0, 3) as citation}
						{@const sourceDomain = getSourceDomain(citation?.sourceUrl)}
						{#if sourceDomain}
							<img
								src="https://www.google.com/s2/favicons?sz=32&domain={sourceDomain}"
								alt="favicon"
								class="size-4 rounded-full shrink-0 border border-white dark:border-gray-850 bg-white dark:bg-gray-900"
							/>
						{/if}
					{/each}
				</div>
			{/if}
			<div>
				{#if citations.length === 1}
					{$i18n.t('1 Source')}
				{:else}
					{$i18n.t('{{COUNT}} Sources', {
						COUNT: citations.length
					})}
				{/if}
			</div>
			</button>
		</div>
	{/if}
