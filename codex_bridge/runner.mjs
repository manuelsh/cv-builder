import { Codex } from "@openai/codex-sdk";

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

function writeStdout(text) {
  return new Promise((resolve, reject) => {
    process.stdout.write(text, (error) => {
      if (error) {
        reject(error);
        return;
      }
      resolve();
    });
  });
}

async function main() {
  const raw = await readStdin();
  const payload = JSON.parse(raw);

  const codex = new Codex();
  const thread = codex.startThread({
    model: payload.model,
    workingDirectory: payload.cwd || process.cwd(),
    skipGitRepoCheck: true,
    sandboxMode: "read-only",
    approvalPolicy: "never",
    modelReasoningEffort: "low",
    webSearchMode: "disabled",
  });

  const { events } = await thread.runStreamed(payload.prompt);
  let content = "";
  let usage = null;

  for await (const event of events) {
    if (event.type === "item.completed" && event.item.type === "agent_message") {
      content = event.item.text;
    } else if (event.type === "turn.completed") {
      usage = event.usage ?? null;
      break;
    } else if (event.type === "turn.failed") {
      throw new Error(event.error?.message || "Codex turn failed");
    }
  }

  await writeStdout(JSON.stringify({ content, usage }));
  process.exit(0);
}

main().catch((error) => {
  process.stderr.write(String(error?.stack || error));
  process.exit(1);
});
