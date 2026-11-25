"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  role: string;
  is_owner: boolean;
}

export interface UserProfile {
  id: string;
  email: string;
  name: string;
  is_superuser: boolean;
  workspaces: Workspace[];
}

interface AuthContextType {
  user: UserProfile | null;
  workspaces: Workspace[];
  currentWorkspace: Workspace | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isLiveMode: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  signup: (email: string, password: string, name: string, workspaceName?: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  switchWorkspace: (workspaceId: string) => void;
  createWorkspace: (name: string) => Promise<{ success: boolean; workspace?: Workspace; error?: string }>;
  toggleDataMode: () => void;
}

import { API_BASE } from "@/lib/api";

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Demo fallback workspace for offline or initial evaluation review
const DEMO_WORKSPACE: Workspace = {
  id: "ws-demo-eval-001",
  name: "Acme Engineering (Evaluation)",
  slug: "acme-engineering-eval",
  role: "OWNER",
  is_owner: true,
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([DEMO_WORKSPACE]);
  const [currentWorkspace, setCurrentWorkspace] = useState<Workspace | null>(DEMO_WORKSPACE);
  const [isLoading, setIsLoading] = useState(true);
  const [isLiveMode, setIsLiveMode] = useState(false); // Default to Evaluation mode until logged in or toggled
  const router = useRouter();

  const fetchCurrentUser = async (token?: string) => {
    setIsLoading(true);
    try {
      const storedToken = token || localStorage.getItem("devaura_token");
      if (!storedToken) {
        setIsLoading(false);
        return;
      }

      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: {
          Authorization: `Bearer ${storedToken}`,
        },
      });

      if (res.ok) {
        const data: UserProfile = await res.json();
        setUser(data);
        if (data.workspaces && data.workspaces.length > 0) {
          setWorkspaces(data.workspaces);
          // Check if previously selected workspace exists
          const savedWsId = localStorage.getItem("devaura_current_ws_id");
          const matched = data.workspaces.find((w) => w.id === savedWsId);
          setCurrentWorkspace(matched || data.workspaces[0]);
          setIsLiveMode(true); // Switch to live workspace data when authenticated
        }
      } else {
        // Token invalid or expired
        localStorage.removeItem("devaura_token");
        setUser(null);
      }
    } catch {
      // Backend offline: retain demo context
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCurrentUser();
  }, []);

  const login = async (email: string, password: string) => {
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();
      if (!res.ok) {
        return {
          success: false,
          error: data?.detail?.error?.message || data?.detail || "Invalid email or password",
        };
      }

      localStorage.setItem("devaura_token", data.access_token);
      if (data.default_workspace_id) {
        localStorage.setItem("devaura_current_ws_id", data.default_workspace_id);
      }

      setUser(data.user);
      setWorkspaces(data.user.workspaces || []);
      const activeWs = (data.user.workspaces || []).find((w: Workspace) => w.id === data.default_workspace_id) || data.user.workspaces[0];
      setCurrentWorkspace(activeWs || null);
      setIsLiveMode(true);

      return { success: true };
    } catch {
      return { success: false, error: "Network error connecting to Devaura API" };
    }
  };

  const signup = async (email: string, password: string, name: string, workspaceName?: string) => {
    try {
      const res = await fetch(`${API_BASE}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, name, workspace_name: workspaceName }),
      });

      const data = await res.json();
      if (!res.ok) {
        return {
          success: false,
          error: data?.detail?.error?.message || data?.detail || "Registration failed",
        };
      }

      localStorage.setItem("devaura_token", data.access_token);
      if (data.default_workspace_id) {
        localStorage.setItem("devaura_current_ws_id", data.default_workspace_id);
      }

      setUser(data.user);
      setWorkspaces(data.user.workspaces || []);
      const activeWs = (data.user.workspaces || []).find((w: Workspace) => w.id === data.default_workspace_id) || data.user.workspaces[0];
      setCurrentWorkspace(activeWs || null);
      setIsLiveMode(true);

      return { success: true };
    } catch {
      return { success: false, error: "Network error connecting to Devaura API" };
    }
  };

  const logout = async () => {
    try {
      const token = localStorage.getItem("devaura_token");
      if (token) {
        await fetch(`${API_BASE}/auth/logout`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
      }
    } catch {
      // Ignore network errors on logout
    } finally {
      localStorage.removeItem("devaura_token");
      localStorage.removeItem("devaura_current_ws_id");
      setUser(null);
      setWorkspaces([DEMO_WORKSPACE]);
      setCurrentWorkspace(DEMO_WORKSPACE);
      setIsLiveMode(false);
      router.push("/");
    }
  };

  const switchWorkspace = (workspaceId: string) => {
    const ws = workspaces.find((w) => w.id === workspaceId);
    if (ws) {
      setCurrentWorkspace(ws);
      localStorage.setItem("devaura_current_ws_id", ws.id);
    }
  };

  const createWorkspace = async (name: string) => {
    try {
      const token = localStorage.getItem("devaura_token");
      if (!token) return { success: false, error: "Authentication required" };

      const res = await fetch(`${API_BASE}/workspaces`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ name }),
      });

      const data = await res.json();
      if (!res.ok) {
        return {
          success: false,
          error: data?.detail?.error?.message || "Failed to create workspace",
        };
      }

      const newWs: Workspace = {
        id: data.id,
        name: data.name,
        slug: data.slug,
        role: "OWNER",
        is_owner: true,
      };

      setWorkspaces((prev) => [newWs, ...prev]);
      setCurrentWorkspace(newWs);
      localStorage.setItem("devaura_current_ws_id", newWs.id);
      setIsLiveMode(true);

      return { success: true, workspace: newWs };
    } catch {
      return { success: false, error: "Network error connecting to Devaura API" };
    }
  };

  const toggleDataMode = () => {
    setIsLiveMode((prev) => !prev);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        workspaces,
        currentWorkspace,
        isAuthenticated: !!user,
        isLoading,
        isLiveMode,
        login,
        signup,
        logout,
        switchWorkspace,
        createWorkspace,
        toggleDataMode,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
