export type Banner = {
	id: string;
	type: string;
	title?: string;
	content: string;
	url?: string;
	dismissible?: boolean;
	timestamp: number;
};

export type EriConfig = {
	host: string;
	port: number;
	authMethod: string;
	token: string;
	dataSource: string;
	retrievalMethod: string;
};

export type KnowledgeBase = {
	id: string;
	name: string;
	description?: string;
	data?: {
		data_source?: 'local' | 'eri';
		eri_config?: EriConfig;
		[key: string]: unknown;
	};
	meta?: Record<string, unknown>;
	[key: string]: unknown;
};

export enum TTS_RESPONSE_SPLIT {
	PUNCTUATION = 'punctuation',
	PARAGRAPHS = 'paragraphs',
	NONE = 'none'
}
