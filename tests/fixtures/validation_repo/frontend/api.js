import { API_BASE } from './config.js';
import { formatStatus } from './utils.js';
import axios from 'axios';
const logger = require('./logger');

export class ApiClient {
    constructor(baseUrl = API_BASE) {
        this.baseUrl = baseUrl;
    }

    async request(endpoint) {
        logger.info(`Fetching ${endpoint}`);
        return axios.get(`${this.baseUrl}${endpoint}`);
    }
}

export const buildUrl = (path) => {
    return `${API_BASE}/${path}`;
};

export async function fetchHealth() {
    const client = new ApiClient();
    const res = await client.request('/health');
    return formatStatus(res.data);
}
