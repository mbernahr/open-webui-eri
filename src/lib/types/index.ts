export type Banner = {
	id: string;
	type: string;
	title?: string;
	content: string;
	url?: string;
	dismissible?: boolean;
	timestamp: number;
};

export enum TTS_RESPONSE_SPLIT {
	PUNCTUATION = 'punctuation',
	PARAGRAPHS = 'paragraphs',
	NONE = 'none'
}

export interface EriConfig {
	host: string;
	port: number;
	authMethod: string;
	token: string;
	dataSource: string;
	retrievalMethod: string;
}

export interface KnowledgeBase {
	id: string;
	name: string;
	description: string;
	data: {
		file_ids: string[];
		data_source: 'local' | 'eri';
		eri_config?: EriConfig | null;
	};
	access_control?: null | object;
	created_at: number;
	updated_at: number;
}
