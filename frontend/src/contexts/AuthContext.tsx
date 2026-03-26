"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";

interface User {
  id: number;
  username: string;
  role: "admin" | "user";
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (token: string, role: "admin" | "user") => void;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Check local storage on mount
    const storedToken = localStorage.getItem("access_token");
    const storedRole = localStorage.getItem("user_role") as "admin" | "user" | null;
    
    if (storedToken && storedRole) {
      setToken(storedToken);
      // For simplicity, we create a mock user object with just the role
      // In a real app, you might want to fetch the full user profile from /api/auth/me
      setUser({ id: 0, username: "user", role: storedRole });
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    // Protected routes logic
    if (!isLoading) {
      if (!token && pathname !== "/login") {
        router.push("/login");
      } else if (token && pathname === "/login") {
        router.push("/dashboard");
      }
    }
  }, [token, isLoading, pathname, router]);

  const login = (newToken: string, role: "admin" | "user") => {
    localStorage.setItem("access_token", newToken);
    localStorage.setItem("user_role", role);
    setToken(newToken);
    setUser({ id: 0, username: "user", role });
    router.push("/dashboard");
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_role");
    setToken(null);
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
