"use server";
import {createSupabaseServerClient} from "@/lib/supabase/server";import {redirect} from "next/navigation";
export async function signIn(formData:FormData){const s=await createSupabaseServerClient();const {error}=await s.auth.signInWithPassword({email:String(formData.get("email")),password:String(formData.get("password"))});if(error)throw new Error(error.message);redirect("/dashboard")}
export async function signUp(formData:FormData){const s=await createSupabaseServerClient();const {error}=await s.auth.signUp({email:String(formData.get("email")),password:String(formData.get("password"))});if(error)throw new Error(error.message);redirect("/dashboard")}
export async function signOut(){const s=await createSupabaseServerClient();await s.auth.signOut();redirect("/auth")}