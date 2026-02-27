'use client';
import React from 'react';
import { CodeEditor } from './CodeEditor';

interface CodeOutputProps {
  value: string;
}

export function CodeOutput({ value }: CodeOutputProps) {
  return <CodeEditor label="Output" value={value} readOnly />;
}
