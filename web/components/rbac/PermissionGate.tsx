"use client";

import React, { useEffect, useState } from "react";

type Permission = [string, string];

interface PermissionGateProps {
  children: React.ReactNode;
  requiredRoles?: string[];
  requiredPermission?: Permission;
  fallback?: React.ReactNode;
}

export function PermissionGate({
  children,
  requiredRoles,
  requiredPermission,
  fallback = null,
}: PermissionGateProps) {
  const [role, setRole] = useState<string>("viewer");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let mounted = true;
    const run = async () => {
      try {
        const res = await fetch("/api/proxy/api/v1/org/me");
        const data = (await res.json().catch(() => ({}))) as { user?: { role?: string } };
        if (!mounted) return;
        if (data?.user?.role) setRole(String(data.user.role));
      } catch {
        // ignore
      } finally {
        if (mounted) setLoaded(true);
      }
    };
    run();
    return () => {
      mounted = false;
    };
  }, []);

  if (!loaded) {
    return <>{fallback}</>;
  }

  if (requiredRoles && !requiredRoles.includes(role)) {
    return <>{fallback}</>;
  }

  if (requiredPermission) {
    const [resource, action] = requiredPermission;
    const key = `perm_${resource}_${action}`;
    const perms = (typeof window !== "undefined" && localStorage.getItem(key)) || "";
    if (perms !== "allow" && role != "admin") {
      return <>{fallback}</>;
    }
  }

  return <>{children}</>;
}
