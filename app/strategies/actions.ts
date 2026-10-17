"use server";

import { randomUUID } from "node:crypto";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase/server";

const defaultDefinition = (assetClass: "crypto" | "forex") => ({
  asset_classes: [assetClass],
  timeframes: ["1h"],
  enabled_agents: [],
  risk_policy: {},
  execution_policy: { mode: "research" },
});

export async function createStrategy(formData: FormData) {
  const supabase = await createSupabaseServerClient();
  const { data: { user }, error: userError } = await supabase.auth.getUser();
  if (userError || !user) redirect("/auth");

  const { data: membership, error: membershipError } = await supabase
    .from("workspace_members")
    .select("workspace_id")
    .eq("user_id", user.id)
    .limit(1)
    .maybeSingle();
  if (membershipError) throw new Error(`Unable to resolve workspace: ${membershipError.message}`);
  if (!membership) throw new Error("No workspace membership found. Sign out and sign in again, or contact support.");

  const name = String(formData.get("name") ?? "").trim();
  const assetClass = String(formData.get("asset_class") ?? "crypto");
  if (!name || name.length > 120) throw new Error("Strategy name must be between 1 and 120 characters.");
  if (assetClass !== "crypto" && assetClass !== "forex") throw new Error("Asset class must be crypto or forex.");

  const slugBase = name.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80) || "strategy";
  const slug = `${slugBase}-${randomUUID().slice(0, 8)}`;

  const { data: strategy, error: strategyError } = await supabase
    .from("strategies")
    .insert({
      workspace_id: membership.workspace_id,
      name,
      slug,
      asset_class: assetClass,
      status: "draft",
    })
    .select("id")
    .single();
  if (strategyError) throw new Error(`Unable to create strategy: ${strategyError.message}`);

  const { error: versionError } = await supabase.from("strategy_versions").insert({
    strategy_id: strategy.id,
    version: 1,
    definition: defaultDefinition(assetClass as "crypto" | "forex"),
  });
  if (versionError) throw new Error(`Strategy was created but its first version failed: ${versionError.message}`);

  revalidatePath("/strategies");
}

export async function createStrategyVersion(formData: FormData) {
  const supabase = await createSupabaseServerClient();
  const { data: { user }, error: userError } = await supabase.auth.getUser();
  if (userError || !user) redirect("/auth");

  const strategyId = String(formData.get("strategy_id") ?? "");
  const { data: membership, error: membershipError } = await supabase
    .from("workspace_members")
    .select("workspace_id")
    .eq("user_id", user.id)
    .limit(1)
    .maybeSingle();
  if (membershipError) throw new Error(`Unable to resolve workspace: ${membershipError.message}`);
  if (!membership) throw new Error("No workspace membership found.");

  const { data: strategy, error: strategyError } = await supabase
    .from("strategies")
    .select("id,asset_class")
    .eq("id", strategyId)
    .eq("workspace_id", membership.workspace_id)
    .maybeSingle();
  if (strategyError) throw new Error(`Unable to load strategy: ${strategyError.message}`);
  if (!strategy) throw new Error("Strategy not found in your workspace.");

  const { data: latest, error: latestError } = await supabase
    .from("strategy_versions")
    .select("version")
    .eq("strategy_id", strategyId)
    .order("version", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (latestError) throw new Error(`Unable to load strategy versions: ${latestError.message}`);

  const { error: insertError } = await supabase.from("strategy_versions").insert({
    strategy_id: strategyId,
    version: (latest?.version ?? 0) + 1,
    definition: defaultDefinition(strategy.asset_class as "crypto" | "forex"),
  });
  if (insertError) throw new Error(`Unable to create strategy version: ${insertError.message}`);

  revalidatePath("/strategies");
}
