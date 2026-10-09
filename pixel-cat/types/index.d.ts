// The latest tool call of the running turn, or null once the turn is over.
export type LastTool = string | null

declare module 'claude-code' {
  interface PluginState {
    'pixel-cat': { lastTool: LastTool }
  }
}
