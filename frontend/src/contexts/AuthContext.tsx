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
  login: (access: string, refresh: string, user: User) => void;
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
    const hydrate = async () => {
      const storedToken = localStorage.getItem("access_token");
      if (storedToken) {
        setToken(storedToken);
        try {
          const authUrl = process.env.NEXT_PUBLIC_AUTH_URL || "http://localhost:8001";
          const res = await fetch(`${authUrl}/auth/me/`, {
            headers: { "Authorization": `Bearer ${storedToken}` }
          });
          if (res.ok) {
            const userData = await res.json();
            setUser(userData);
          } else {
            logout();
          }
        } catch (err) {
          console.error("Hydration failed", err);
          logout();
        }
      }
      setIsLoading(false);
    };
    hydrate();
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

  const login = (access: string, refresh: string, userData: User) => {
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
    setToken(access);
    setUser(userData);
    router.push("/dashboard");
  };

  const logout = async () => {
    const refresh = localStorage.getItem("refresh_token");
    if (refresh) {
      try {
        const authUrl = process.env.NEXT_PUBLIC_AUTH_URL || "http://localhost:8001";
        await fetch(`${authUrl}/auth/logout/`, {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}` 
          },
          body: JSON.stringify({ refresh })
        });
      } catch (err) {
        console.error("Logout API failed", err);
      }
    }
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
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
