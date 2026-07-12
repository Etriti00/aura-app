import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
	base: './',
	plugins: [react(), viteSingleFile({ inlinePattern: ['**/*.js', '**/*.css'] })],
});
