import { ApiClient } from './api.js';

export interface UserProfile {
    id: string;
    username: string;
    email: string;
    role: UserRole;
    isActive: boolean;
}

export type UserRole = 'admin' | 'user' | 'guest';

export class UserManager {
    private client: ApiClient;

    constructor() {
        this.client = new ApiClient();
    }

    async getUserProfile(userId: string): Promise<UserProfile> {
        const response = await this.client.request(`/users/${userId}`);
        return response.data as UserProfile;
    }
}

export function formatUserDisplay(profile: UserProfile): string {
    return `${profile.username} (${profile.role})`;
}
