import { useState } from 'react'

export type ProviderId = 'openai' | 'anthropic'

export type LLMProviderStatus = {
  id: ProviderId
  display_name: string
  api_key_configured: boolean
  models: string[]
}

export type LLMSettings = {
  configured: boolean
  onboarding_complete: boolean
  selected_provider: ProviderId | null
  selected_model: string | null
  providers: LLMProviderStatus[]
  credential_store_error: string | null
}

type Props = {
  setupToken: string
  settings: LLMSettings
  mode: 'onboarding' | 'settings'
  onChange: (settings: LLMSettings) => void
}

async function readApiError(response: Response) {
  const body = (await response.json().catch(() => null)) as { detail?: string } | null
  return body?.detail ?? 'The request could not be completed. Try again.'
}

export function LLMConfiguration({ setupToken, settings, mode, onChange }: Props) {
  const initialProvider = settings.selected_provider ?? 'openai'
  const [provider, setProvider] = useState<ProviderId>(initialProvider)
  const [model, setModel] = useState(settings.selected_model ?? '')
  const [apiKey, setApiKey] = useState('')
  const [isReplacingKey, setIsReplacingKey] = useState(false)
  const [providerStates, setProviderStates] = useState(settings.providers)
  const [isFetching, setIsFetching] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isForgetting, setIsForgetting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const providerState = providerStates.find(item => item.id === provider)!

  const chooseProvider = (nextProvider: ProviderId) => {
    setProvider(nextProvider)
    const nextState = providerStates.find(item => item.id === nextProvider)!
    setModel(settings.selected_provider === nextProvider ? settings.selected_model ?? '' : nextState.models[0] ?? '')
    setApiKey('')
    setIsReplacingKey(false)
    setError(null)
    setNotice(null)
  }

  const fetchModels = async () => {
    setIsFetching(true)
    setError(null)
    setNotice(null)
    try {
      const response = await fetch(`/api/llm/providers/${provider}/models`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Jeromes-Lab-Setup-Token': setupToken,
        },
        body: JSON.stringify({ api_key: apiKey.trim() || null }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      const result = (await response.json()) as { provider: ProviderId, models: string[] }
      setProviderStates(current => current.map(item => item.id === result.provider
        ? { ...item, api_key_configured: true, models: result.models }
        : item))
      if (!result.models.includes(model)) setModel(result.models[0] ?? '')
      setApiKey('')
      setIsReplacingKey(false)
      setNotice(`${result.models.length} compatible model${result.models.length === 1 ? '' : 's'} found. The API key is stored securely on this device.`)
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'The model list could not be fetched.')
    } finally {
      setIsFetching(false)
    }
  }

  const saveSelection = async () => {
    if (!model) return
    setIsSaving(true)
    setError(null)
    try {
      const response = await fetch('/api/llm/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Jeromes-Lab-Setup-Token': setupToken,
        },
        body: JSON.stringify({ provider, model }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onChange(await response.json() as LLMSettings)
      setNotice(`Future LLM jobs will use ${providerState.display_name} · ${model}.`)
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'The provider settings could not be saved.')
    } finally {
      setIsSaving(false)
    }
  }

  const skipSetup = async () => {
    setIsSaving(true)
    setError(null)
    try {
      const response = await fetch('/api/llm/settings/skip', {
        method: 'POST',
        headers: { 'X-Jeromes-Lab-Setup-Token': setupToken },
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onChange(await response.json() as LLMSettings)
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Provider setup could not be skipped.')
    } finally {
      setIsSaving(false)
    }
  }

  const forgetApiKey = async () => {
    setIsForgetting(true)
    setError(null)
    try {
      const response = await fetch(`/api/llm/providers/${provider}/api-key`, {
        method: 'DELETE',
        headers: { 'X-Jeromes-Lab-Setup-Token': setupToken },
      })
      if (!response.ok) throw new Error(await readApiError(response))
      const updated = await response.json() as LLMSettings
      setProviderStates(updated.providers)
      setModel('')
      setApiKey('')
      setIsReplacingKey(false)
      setNotice(`${providerState.display_name} API key forgotten on this device.`)
      onChange(updated)
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'The API key could not be forgotten.')
    } finally {
      setIsForgetting(false)
    }
  }

  return <div className={`llm-configuration llm-configuration--${mode}`}>
    {settings.credential_store_error && <p className="setup-error" role="alert">{settings.credential_store_error} You can configure the provider later.</p>}
    <fieldset className="provider-options">
      <legend>Provider</legend>
      {providerStates.map(item => <label key={item.id} className={provider === item.id ? 'provider-option provider-option--selected' : 'provider-option'}>
        <input type="radio" name={`provider-${mode}`} value={item.id} checked={provider === item.id} onChange={() => chooseProvider(item.id)} />
        <span>{item.display_name}</span>
      </label>)}
    </fieldset>

    <label htmlFor={`api-key-${mode}`}>{providerState.display_name} API key</label>
    <input
      id={`api-key-${mode}`}
      className="configuration-input"
      type="password"
      autoComplete="off"
      value={apiKey}
      onChange={event => setApiKey(event.target.value)}
      disabled={providerState.api_key_configured && !isReplacingKey}
      placeholder={providerState.api_key_configured && !isReplacingKey ? 'API key securely stored' : 'Paste API key'}
    />
    <div className="configuration-actions">
      <button className="secondary-button" type="button" onClick={() => void fetchModels()} disabled={isFetching || (isReplacingKey ? !apiKey.trim() : !apiKey.trim() && !providerState.api_key_configured)}>
        {isFetching ? 'Fetching models…' : isReplacingKey ? 'Validate and save new key' : providerState.api_key_configured ? 'Refresh models' : 'Fetch models'}
      </button>
      {providerState.api_key_configured && !isReplacingKey && <button className="text-button" type="button" onClick={() => { setIsReplacingKey(true); setApiKey(''); setError(null); setNotice(null) }}>Change key</button>}
      {providerState.api_key_configured && isReplacingKey && <button className="text-button" type="button" onClick={() => { setIsReplacingKey(false); setApiKey(''); setError(null) }}>Cancel key change</button>}
      {providerState.api_key_configured && <button className="text-button" type="button" onClick={() => void forgetApiKey()} disabled={isForgetting}>
        {isForgetting ? 'Forgetting…' : 'Forget API key'}
      </button>}
    </div>

    <label htmlFor={`model-${mode}`}>Default model</label>
    <select id={`model-${mode}`} className="configuration-input" value={model} onChange={event => setModel(event.target.value)} disabled={providerState.models.length === 0}>
      {providerState.models.length === 0 && <option value="">Fetch models to continue</option>}
      {providerState.models.map(modelId => <option key={modelId} value={modelId}>{modelId}</option>)}
    </select>

    {notice && <p className="setup-notice" role="status">{notice}</p>}
    {error && <p className="setup-error" role="alert">{error}</p>}

    <div className="configuration-actions configuration-actions--final">
      <button className="primary-button" type="button" onClick={() => void saveSelection()} disabled={!model || isSaving}>
        {isSaving ? 'Saving…' : mode === 'onboarding' ? 'Save and continue' : 'Save provider and model'}
      </button>
      {mode === 'onboarding' && <button className="text-button" type="button" onClick={() => void skipSetup()} disabled={isSaving}>Configure later</button>}
    </div>
  </div>
}
