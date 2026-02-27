'use client';
import { useState, useEffect } from 'react';
import { getHealth } from '../api';

export function useHealth() {
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    getHealth()
      .then(() => setHealthy(true))
      .catch(() => setHealthy(false));
  }, []);

  return healthy;
}
