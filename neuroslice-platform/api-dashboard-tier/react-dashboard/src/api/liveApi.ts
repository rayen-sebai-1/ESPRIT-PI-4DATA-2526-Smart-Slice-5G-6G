import { axiosInstance } from './axios';

export interface LiveOverview {
    total_entities: number;
    active_faults_count: number;
    unhealthy_entities_count: number;
    congestion_alerts_count: number;
    sla_risk_count: number;
    slice_mismatch_count: number;
    latest_entities: any[];
    latest_aiops_events: any[];
}

export const liveApi = {
    getOverview: async (): Promise<LiveOverview> => {
        const response = await axiosInstance.get('/api/v1/live/overview');
        return response.data;
    },
    getEntities: async (limit: number = 100): Promise<{ count: number; items: any[] }> => {
        const response = await axiosInstance.get(`/api/v1/live/entities?limit=${limit}`);
        return response.data;
    },
    getEntity: async (entityId: string): Promise<any> => {
        const response = await axiosInstance.get(`/api/v1/live/entities/${entityId}`);
        return response.data;
    },
    getEntityAiops: async (entityId: string): Promise<any> => {
        const response = await axiosInstance.get(`/api/v1/live/entities/${entityId}/aiops`);
        return response.data;
    },
    getFaults: async (): Promise<{ faults: any[] }> => {
        const response = await axiosInstance.get('/api/v1/live/faults');
        return response.data;
    }
};
