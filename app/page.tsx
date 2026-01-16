import { redirect } from "next/navigation";

export default function HomePage() {
    // Redirect to upload page - Dashboard removed
    redirect("/upload");
}

