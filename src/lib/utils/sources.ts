const EXTERNAL_HTTP_URL_REGEX = /^https?:\/\//i;

const asNonEmptyString = (value: unknown): string | null => {
	if (typeof value !== 'string') return null;
	const trimmed = value.trim();
	return trimmed.length > 0 ? trimmed : null;
};

const isExternalHttpUrl = (value: unknown): value is string => {
	const candidate = asNonEmptyString(value);
	return candidate !== null && EXTERNAL_HTTP_URL_REGEX.test(candidate);
};

export const getSourceUrl = (source: Record<string, unknown> | null | undefined): string | null => {
	if (!source || typeof source !== 'object') return null;

	const links = source?.links;
	if (Array.isArray(links) && links.length > 0 && isExternalHttpUrl(links[0])) {
		return links[0];
	}

	if (isExternalHttpUrl(source?.path)) {
		return source.path;
	}

	// Backward compatibility for existing source payloads that expose `url`.
	if (isExternalHttpUrl(source?.url)) {
		return source.url;
	}

	return null;
};
