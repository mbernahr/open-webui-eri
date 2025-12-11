
<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount } from "svelte";
    import AccessControl from "../common/AccessControl.svelte";
    import { currentChatPage } from "$lib/stores";

  type DataSourceInfo = {
    name: string;
    description: string;
  };

  type RetrievalInfo = {
    id: string;
    name: string;
    description: string;
    link: string;
    parametersDescription: Record<string, string>;
    embeddings: {
      embeddingType: string;
      embeddingName: string;
      description: string;
      usedWhen: string;
      link: string;
    }[];
  };

  type SecurityRequirements = {
    allowedProviderType: string;
  }

  export let knowledgeId: string | null = null;

  export let host: string = '';
  export let port: number = 0;
  let base = '';

  let authMethods = [] as { authMethod: string; authFieldMappings: any[] }[];
  export let authMethod: string = '';
  export let token: string = '';
  let accessToken = '';
  let usernameInput = '';
  let passwordInput = '';
  let sessionToken = '';

  let testStatus: 'idle' | 'success' | 'error' = 'idle';
  let testMessage = '';
  let hydrated = false;

  let dataSource: DataSourceInfo | null = null;
  export let selectedSource: string = '';
  let dataDescription = '';
  
  let retrievalMethods: RetrievalInfo[] = [];
  export let selectedMethod: string = '';

  let securityPolicy: SecurityRequirements | null = null;
  let selectedPolicy = '';
  let pingTimer: any = null;

  let abortCtrl: AbortController | null = null;

  let reauthing = false;

  const dispatch = createEventDispatcher();

  function buildBaseUrl(): string {
    if (!host  || !port) return '';
    let b = host.replace(/\/$/, '') + ':' + port;
    if (!/^https?:\/\//.test(b)) {
      b = `http://${b}`;
    }
    return b 
  }

  function debounce<T extends (...a: any) => void>(fn: T, wait = 400) {
    let timer: ReturnType<typeof setTimeout>;
    return (...args: Parameters<T>) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), wait);
    };
  }

  const debouncedLoadAuth = debounce(loadAuthMethods, 400);

  $: base = buildBaseUrl();
  
  $: if (base && token && !dataSource && retrievalMethods.length === 0) {
    sessionToken = token;
    loadProtectedData();
  } 

  $: {
    if (host.trim() && /^\d{2,5}$/.test(String(port))) {
      debouncedLoadAuth();
    } 
  }

  onMount(() => {
    base = buildBaseUrl();
    if (!hydrated && token?.trim() && base) {
      sessionToken = token;
      verifyAnyLoad();
    }
    pingTimer = setInterval(async () => {
      if (!sessionToken || !base) return;
      const ok = await tryHeadOrGet(`${base}/dataSource`);
      if (!ok) handleAuthLost('Session expirded or invalid.');
    }, 60000);
  });

  $: if (hydrated && (!token?.trim() || !authMethod)) {
    hydrated = false;
    testStatus = 'idle';
    testMessage = '';
    sessionToken = '';
  }

  onDestroy(() => debouncedLoadAuth.cancel?.());
  onDestroy(() => {
    abortCtrl?.abort();
    if (pingTimer) clearInterval(pingTimer);
  });

  async function loadAuthMethods() {
    base = buildBaseUrl();
    if (!base) return;

    abortCtrl?.abort();
    abortCtrl = new AbortController();

    try {
      // Auth
      const resAuth = await fetch(`${base}/auth/methods`, {
        signal: abortCtrl.signal,
      });
      if (!resAuth.ok) throw new Error(`HTTP ${resAuth.status}`);
      
      const methods = await resAuth.json();
      authMethods = methods;

      const current = authMethod;

      if (
        !current ||
        !authMethods.some((m) => m.authMethod === current)
      ) {
        authMethod = authMethods[0]?.authMethod ?? '';
      }
    } catch (e) {
      if (e.name === 'AbortError') return;
      console.error('Error loading auth methods:', e);
    }
  }

  function getAuthHeaders(): Record<string,string> {
    const h: Record<string,string> = { 'Accept': 'application/json'};
    if (sessionToken) {
      h.Authorization = `Bearer ${sessionToken}`;
      h.token = sessionToken;
    }
    return h;
  }

  async function tryHeadOrGet(url: string): Promise<boolean> {
    try {
      const res = await fetch(url, { method: 'GET', headers: getAuthHeaders() });
      if (res.status === 401) return false;
      return res.ok;
    } catch {
      return false;
    }
  }

  async function reauthViaBackend(): Promise<boolean> {
    if (!knowledgeId) return false;
      try {
        const res = await fetch(`/api/v1/knowledge/${knowledgeId}/eri/ensure`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${localStorage.token}`
          },
        });
        if (!res.ok) return false;
        const kb = await res.json();
        const cfg = kb?.data?.eri_config;
        if (cfg) {
          host = cfg.host ?? host;
          port = cfg.port ?? port;
          authMethod = cfg.authMethod ?? authMethod;
          token = cfg.token ?? token;
          sessionToken = cfg.token ?? sessionToken;
          selectedSource = cfg.dataSource ?? selectedSource;
          selectedMethod = cfg.retrievalMethod ?? selectedMethod;
        }
        return true;
      } catch (e) {
        console.error('ERI reauth failed', e);
        return false;
      }    
  }

  async function handleAuthLost(msg = 'Authentication failed or expired.') {
    if (knowledgeId && !reauthing) {
      reauthing = true;
      const ok = await reauthViaBackend();
      reauthing = false;

      if (ok) {
        const ok2 = await loadProtectedData();
        if (ok2) {
          testStatus = 'success';
          testMessage = 'Authenticated';
          hydrated = true;
          return;
        }
      }
    }

    testStatus = 'error';
    testMessage = msg;
    hydrated = false;
  }

  async function verifyAnyLoad() {
    testStatus = 'idle'; testMessage = '';
    const ok = await loadProtectedData();
    if (ok) {
      testStatus = 'success'; testMessage = 'Authentication successful'; hydrated = true;
    } else handleAuthLost();
  }

  onDestroy(() => abortCtrl?.abort());

  async function testConnection() {
    testStatus = 'idle';
    testMessage = '';

    if (!base) {
      testStatus = 'error';
      testMessage = 'Please enter host and port.';
      return;
    }

    try {
      const url = `${base}/auth?authMethod=${encodeURIComponent(authMethod)}`;
      const headers: Record<string,string> = { 'Accept': 'application/json'};
      if (authMethod === 'TOKEN') {
        headers['Authorization'] = `Bearer ${accessToken}`;
      } else if (authMethod === 'USERNAME_PASSWORD') {
        headers['user'] = usernameInput;
        headers['password'] = passwordInput;
      }

      const resTest = await fetch(url, {
        method: 'POST',
        headers,
        body: ''
      });
      const body = await resTest.json();
      if (resTest.ok && body.success) {
        sessionToken = body.token;
        token = sessionToken;
        testMessage = body.message ?? 'Connection successfull.';

        const ok = await loadProtectedData();
        if (ok) {
          testStatus = 'success';
          testMessage = body.message ?? 'Authentication successful'
        } else {
          testStatus = 'error';
          testMessage = 'Authentication failed or expired'
        }

      } else {
        testStatus = 'error';
        if (body.detail) {
          if(typeof body.detail === 'string') {
            testMessage = body.detail;
          } else if (Array.isArray(body.detail)) {
            testMessage = body
              .detail
              .map((e: any) => e.msg || JSON.stringify(e))
              .join('; ');
          } else {
            testMessage = JSON.stringify(body.detail);
          }
        } else if (body.message) {
          testMessage = body.message;
        } else {
          testMessage = `HTTP ${resTest.status}`;
        }
      }
    } catch (e) {
      testStatus = 'error';
      testMessage = e instanceof Error ? e.message : String(e);
    }
  }

  async function loadProtectedData(): Promise<boolean> {
    let allOK = true;
    try {
      // Data Source
      const resSource = await fetch(`${base}/dataSource`, {
        method: 'GET',
        headers: getAuthHeaders()
      });
      if (!resSource.ok) throw new Error(`HTTP ${resSource.status}`);
      dataSource = await resSource.json();
      selectedSource = dataSource?.name ?? '';
      dataDescription = dataSource?.description ?? 'No description available.';
    } catch (e) {
      console.error('DataSource error:', e);
      dataDescription = `Error loading data source: ${e instanceof Error ? e.message : String(e)}`;
      if (String(e).includes('401')) allOK = false;
    }

    
    try {
      // Retrieval Method
      const resRetrieval = await fetch(`${base}/retrieval/info`, {
        method: 'GET',
        headers: getAuthHeaders()
      });
      if (!resRetrieval.ok) throw new Error(`HTTP ${resRetrieval.status}`);
      retrievalMethods = await resRetrieval.json();
      if (retrievalMethods.length > 0) {
      selectedMethod = retrievalMethods[0].name;
      }
    } catch (e) {
      console.error('Retrieval info error:', e);
      dataDescription += `\nError loading retrieval methods: ${e instanceof Error ? e.message : String(e)}`;
      if (String(e).includes('401')) allOK = false;
    }


    try {
      // Security Policy
      const resSecurity = await fetch(`${base}/security/requirements`, {
        method: 'GET',
        headers: getAuthHeaders()
      });
      if (!resSecurity.ok) throw new Error(`HTTP ${resSecurity.status}`);
      securityPolicy = await resSecurity.json();
      selectedPolicy  = securityPolicy?.allowedProviderType ?? '';
    } catch (e) {
      console.error('Security requirements error:', e);
      dataDescription += `\nError loading security requirements: ${e instanceof Error ? e.message : String(e)}`;
      if (String(e).includes('401')) allOK = false;
    }
    return allOK;
  }

  $: selectedRetrieval = retrievalMethods.find(m => m.name === selectedMethod);

  function handleSave() {
    const secret: any = { authMethod };
    if (authMethod === 'TOKEN') {
      secret.access_token = accessToken;
    } else if (authMethod === 'USERNAME_PASSWORD') {
      secret.username = usernameInput;
      secret.password = passwordInput;
    }
    dispatch('finish', {secret});
  }
</script>

<style>
  .container {
    display: flex;
    position: relative;
    min-height: 100%;
    flex-direction: row;
    align-items: flex-start;
    justify-content: center; 
    width: 100%;
  }

  .panel {
    width: 24rem; /* Fixed width for the panel */
    padding: 1rem;
    display: flex;
    flex-direction: column;
  }

  .panel h2 {
    margin-bottom: 1rem;
    font-size: 1.25rem;
    font-weight: 600;
  }

  .description {
    flex: 1; /* Takes remaining space */
    margin-left: 0; /* Remove left margin since it's now floated right */
    width: 30%;
    max-width: 24rem; 
    display: flex;
    flex-direction: column;
    padding: 1rem;
  }

  .description h2 {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
  }

  .description p {
    font-size: .875rem;
    color: #374151;
    white-space: pre-wrap;
  }

  .row {
    display: flex;
    flex-direction: column;
    margin-bottom: 1rem;
  }

  .row label {
    margin-bottom: 0.25rem;
    font-weight: 500;
    color: #4b5563;
  }

  .btn {
    padding: 0.5rem 1rem;
    border-radius: 0.25rem;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
  }

  .actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 1rem;
  }

  .info {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    margin-top: 1rem;
    margin-bottom: 1rem;
    color: #374151;
    font-size: 0.875rem;
  }

  .info-icon {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.25rem;
    height: 1.25rem;
    border: 1px solid #6b7280;
    border-radius: 50%;
    color: #6b7280;
    font-size: 0.75rem;
    font-weight: bold;
    line-height: 1.25rem;
  }

  .test-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
    justify-content: flex-start;
  }

  .row.test-row {
    flex-direction: row;
    align-items: center;
    gap: 0.5rem;
  }

  .msg {
    display: inline-block;
    max-width: 12rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    vertical-align: middle;
  }
</style>

<div class="container">
  <div class="panel">
    <h2>(E)xternal (R)etrieval (I)nterface</h2>

    <form on:submit|preventDefault>
      <div class="row">
        <label for="host">Server host name</label>
        <input id="host" bind:value={host} type="text" placeholder="http://…" class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden" />
      </div>

      <div class="row">
        <label for="port">Port</label>
        <input id="port" bind:value={port} type="number" placeholder="40304" class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden" />
      </div>

      <div class="row">
        <label for="auth">Authentication</label>
        <select id="auth" bind:value={authMethod} class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden">
          {#if authMethods.length === 0}
            <option disabled selected value="">Select Authentication Method</option>
          {:else}
            {#each authMethods as m}
              <option value={m.authMethod}>{m.authMethod}</option>
            {/each}
          {/if}
        </select>
      </div>

      {#if authMethod === 'TOKEN'}
        <div class="row">
          <label for="token">Access Token</label>
          <input id="token" bind:value={accessToken} type="text" class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden" />
        </div>
      {:else if authMethod === 'USERNAME_PASSWORD'}
        <div class="row">
          <label for="user">Username</label>
          <input id="user" bind:value={usernameInput} type="text" placeholder="user" class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"/>
        </div>
        <div class="row">
          <label for="pass">Password</label>
          <input id="pass" bind:value={passwordInput} type="password" placeholder="password" class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"/>
        </div>
      {/if}

      <div class="row test-row">
        <button type="button" class="btn bg-gray-50 hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800" on:click={testConnection}>
          Test connection
        </button>
        {#if testStatus === 'success' && testMessage}
          <span class="msg" style="color: green; font-size: 0.875rem;">{testMessage}</span>
        {:else if testStatus === 'error' && testMessage}
          <span class="msg" style="color: red; font-size: 0.875rem;">{testMessage}</span>
        {/if}
      </div>

      <div class="row">
        <label for="source">Data Source</label>
        <select id="source" bind:value={selectedSource} class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden">
          {#if !dataSource}
            <option disabled selected value="">Select Data Source</option>
          {/if}
          {#if dataSource}
            <option value={dataSource?.name}>{dataSource.name}</option>
          {/if}
        </select>
      </div>

      <div class="row">
        <label for="method">Retrieval Method</label>
          <select id="method" bind:value={selectedMethod} class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden">
          {#if retrievalMethods.length === 0}
            <option disabled selected value="">Select Retrieval Method</option>
          {:else}
            {#each retrievalMethods as m}
              <option value={m.name}>{m.name}</option>
            {/each}
          {/if}
        </select>
      </div>

      {#if selectedRetrieval}
        <div class="info">
          <div class="info-icon">i</div>
          <div>{selectedRetrieval.description ?? 'No description available.'}</div>
        </div>
      {:else}
        <div class="info">
          <div class="info-icon">i</div>
          <div>Description of the retrieval method.</div>
        </div>
      {/if}
    

      <div class="row">
        <label for="policy">Security Policy</label>
        <div class="info">
          <div class="info-icon">i</div>
          <div>
            {#if securityPolicy}
              This interface is restricted to LLMs of type: <strong>{securityPolicy.allowedProviderType}</strong>
            {:else}
              Information about the security requirements for allowed LLM providers.
          {/if}
          </div>
        </div>
      </div>

      <div class="actions">
        <button type="button" class="btn bg-gray-50 hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800" on:click={handleSave}>
          Save &amp; return</button>
      </div>
    </form>
  </div>

  {#if dataDescription}
    <div class="description">
      <h2>{dataDescription.startsWith('Error') ? 'Error Message' : 'Data Description'}</h2>
      <p>{dataDescription}</p>
    </div> 
  {/if}   
</div>