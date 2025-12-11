<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount, getContext } from 'svelte';
	const i18n = getContext('i18n');

	import { getGroups } from '$lib/apis/groups';

	import { createNewKnowledge, getKnowledgeBases } from '$lib/apis/knowledge';
	import { toast } from 'svelte-sonner';
	import { knowledge, user } from '$lib/stores';
	import AccessControl from '../common/AccessControl.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	import EriSetupPanel from './EriSetupPanel.svelte';
	import type { EriConfig } from '$lib/types';
	let loading = false;

	let name = '';
	let description = '';
	type Access = Record<string, unknown>;
	let accessControl: Access = {};

	let tags: string[] = [];
	let tagInput = '';
	let showTagInput = false;

	let groups: { id: string; name: string }[] = [];

	let dataSource: 'local' | 'eri' = 'local';

	let showEriSetup = false;

	let eriPanelHost = '';
	let eriPanelPort = 0;
	let authMethod = '';
	let eriPanelToken = '';
	let eriPanelSelectedSource = '';
	let eriPanelSelectedMethod = '';

	let eriSetupDone = false;

	let eriPanelSecret: any = null;

	const submitHandler = async () => {
		loading = true;

		if (name.trim() === '' || description.trim() === '') {
			toast.error($i18n.t('Please fill in all fields.'));
			name = '';
			description = '';
			loading = false;
			return;
		}

		if (dataSource === 'eri' && !eriSetupDone) {
			showEriSetup = true;
			loading = false;
			return;
		}

		const ac = accessControl; 
		let res;

		let eriConfig: EriConfig | undefined;
		if (dataSource === 'eri') {
			eriConfig = {
				host: eriPanelHost.trim(),
				port: Number(eriPanelPort),
				authMethod,
				token: eriPanelToken.trim(),
				dataSource: eriPanelSelectedSource,
				retrievalMethod: eriPanelSelectedMethod
			} as EriConfig;
		}

		res = await createNewKnowledge(
			localStorage.token,
			name,
			description,
			ac,
			{
				data_source: dataSource,
				eri_config: eriConfig,
			}
		).catch((e) => {
			toast.error(`${e}`);
		});

		if (res) {
			toast.success($i18n.t('Knowledge created successfully.'));
			knowledge.set(await getKnowledgeBases(localStorage.token));
			
			if (dataSource === 'eri' && eriPanelSecret) {
				await fetch(`/api/v1/knowledge/${res.id}/eri/credentials`, {
					method: 'POST',
					headers: {
						'Content-Type': 'application/json',
						Authorization: `Bearer ${localStorage.token}`
					},
					body: JSON.stringify(eriPanelSecret)
				}).catch(() => {});
			} 

			goto(`/workspace/knowledge/${res.id}`);
		}

		loading = false;
	};

	onMount(async () => {
		const resGroups = await getGroups(localStorage.token);
		if (resGroups) {
			groups = resGroups;
		}
	});

	const addTag = () => {
		if (tagInput.trim() && !tags.includes(tagInput.trim())) {
			tags = [...tags, tagInput.trim()];
			tagInput = '';
		}
	};

	const removeTag = (tagToRemove: string) => {
		tags = tags.filter((t) => t !== tagToRemove);
	};
</script>

<style>
	.panel-wrapper {
		padding: 1.5rem;
		max-width: 36rem;
		margin: 2rem auto;
	}
	
	input, textarea, select {
		padding: 0.5rem 0.75rem;
		font-size: 0.875rem;
		outline: none;
	}

</style>


<div class="w-full max-h-full">
	<button
		class="flex space-x-1"
		on:click={() => {
			goto('/workspace/knowledge');
		}}
	>
		<div class=" self-center">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				viewBox="0 0 20 20"
				fill="currentColor"
				class="w-4 h-4"
			>
				<path
					fill-rule="evenodd"
					d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z"
					clip-rule="evenodd"
				/>
			</svg>
		</div>
		<div class=" self-center font-medium text-sm">{$i18n.t('Back')}</div>
	</button>

	{#if !showEriSetup}
		<div class="panel-wrapper">	
			<form
				class="flex flex-col max-w-lg mx-auto mt-10 mb-10"
				on:submit|preventDefault={() => {
					submitHandler();
				}}
			>
				<div class=" w-full flex flex-col justify-center">
					<div class=" text-2xl font-medium font-primary mb-2.5">
						{$i18n.t('Create a knowledge base')}
					</div>

					<div class="w-full flex flex-col gap-2.5">
						<div class="w-full">
							<div class=" text-sm mb-2">{$i18n.t('What are you working on?')}</div>

							<div class="w-full mt-1">
								<input
									class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
									type="text"
									bind:value={name}
									placeholder={$i18n.t('Name your knowledge base')}
									required
								/>
							</div>
						</div>

						<div>
							<div class="text-sm mb-2">{$i18n.t('What are you trying to achieve?')}</div>

							<div class=" w-full mt-1">
								<textarea
									class="w-full resize-none rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
									rows="4"
									bind:value={description}
									placeholder={$i18n.t('Describe your knowledge base and objectives')}
									required
								/>
							</div>
						</div>
					</div>
				</div>

				<div class="mt-4">
					<div class="flex items-center gap-2 text-sm mb-2">
						<!-- Plus Button -->
						<button
							class="w-6 h-6 flex items-center justify-center rounded-full bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600"
							type="button"
							on:click={() => (showTagInput = !showTagInput)}
						>
							<span class="text-sm font-bold">+</span>
						</button>
						<span>{$i18n.t('Add Tags')}</span>
					</div>

					{#if showTagInput}
						<div class="mt-2 flex gap-2 items-center">
							<input
								class="w-full text-sm dark:text-gray-300 dark:bg-gray-850 outline-hidden"
								type="text"
								bind:value={tagInput}
								placeholder="Add a tag and press Enter"
								on:keydown={(e) => {
									if (e.key === 'Enter') {
										e.preventDefault();
										addTag();
										showTagInput = false; // automatisch einklappen
									}
								}}
							/>

							<button
								class="px-4 h-9 text-sm font-medium bg-gray-900 text-white dark:bg-white dark:text-black rounded-lg hover:bg-gray-700 dark:hover:bg-gray-200 transition whitespace-nowrap"
								type="button"
								on:click={() => {
									addTag();
									showTagInput = false;
								}}
							>
								{$i18n.t('Add')}
							</button>
						</div>
					{/if}

					{#if tags.length > 0}
						<div class="flex flex-wrap mt-2 gap-2">
							{#each tags as tag}
								<div class="flex items-center px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded-full text-xs">
									<span class="mr-2">{tag}</span>
									<button type="button" on:click={() => removeTag(tag)}>✕</button>
								</div>
							{/each}
						</div>
					{/if}
				</div>

				<div class="mt-2">
					<div class="px-3 py-2 bg-gray-50 dark:bg-gray-950 rounded-lg">
						<AccessControl
							bind:accessControl
							accessRoles={['read', 'write']}
							share={$user?.permissions?.sharing?.knowledge || $user?.role === 'admin'}
							sharePublic={$user?.permissions?.sharing?.public_knowledge || $user?.role === 'admin'}
							/>
						</div>
					</div>
	
					<div class="mt-4">
						<div class="text-sm mb-2">{$i18n.t('Data Source')}</div>
	
						<div class="flex gap-4 items-center">
							<label class="flex items-center gap-2">
								<input
									type="radio"
									bind:group={dataSource}
									value="local"
									class="accent-black dark:accent-white"
								/>
								<span class="text-sm">Local Data</span>
							</label>
	
							<label class="flex items-center gap-2">
								<input
									type="radio"
									bind:group={dataSource}
									value="eri"
									class="accent-black dark:accent-white"
								/>
								<span class="text-sm">ERI</span>
							</label>
						</div>
	
						<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
							{#if dataSource === 'local'}
								{$i18n.t('Use documents uploaded from your computer')}
							{:else}
								{$i18n.t('Use ERI integration as a data source')}
							{/if}
						</div>
					</div>


				<div class="flex justify-end mt-2">
					<div>
						<button
							class=" text-sm px-4 py-2 transition rounded-lg {loading
								? ' cursor-not-allowed bg-gray-100 dark:bg-gray-800'
								: ' bg-gray-50 hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800'} flex"
							type="submit"
							disabled={loading}
						>
							<div class=" self-center font-medium">{$i18n.t('Create Knowledge')}</div>

							{#if loading}
								<div class="ml-1.5 self-center">
									<Spinner />
								</div>
							{/if}
						</button>
					</div>
				</div>
			</form>
		</div>
	{/if}	
	{#if showEriSetup}
	<EriSetupPanel
		bind:host={eriPanelHost} 
		bind:port={eriPanelPort} 
		bind:authMethod={authMethod}
		bind:token={eriPanelToken}
		bind:selectedSource={eriPanelSelectedSource}
		bind:selectedMethod={eriPanelSelectedMethod}
		on:finish={(e) => {    
			eriSetupDone = true;
			showEriSetup = false;
			eriPanelSecret = e.detail.secret ?? null;
			submitHandler();  
		}}
	/>
	{/if}
</div>
