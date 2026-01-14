import Link from "next/link";
import { ArrowRight, FileText, CheckCircle, BarChart } from "lucide-react";

export default function DashboardPage() {
    return (
        <div className="space-y-8">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-3xl font-bold mb-2">Welcome back</h2>
                    <p className="text-gray-500">Here's what's happening with your documents.</p>
                </div>
                <Link
                    href="/upload"
                    className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center gap-2"
                >
                    New Extraction <ArrowRight className="w-4 h-4" />
                </Link>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white p-6 rounded-xl border shadow-sm">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-blue-50 rounded-lg">
                            <FileText className="w-6 h-6 text-blue-600" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 font-medium">Total Documents</p>
                            <h3 className="text-2xl font-bold">12</h3>
                        </div>
                    </div>
                </div>

                <div className="bg-white p-6 rounded-xl border shadow-sm">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-green-50 rounded-lg">
                            <CheckCircle className="w-6 h-6 text-green-600" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 font-medium">Successful Extractions</p>
                            <h3 className="text-2xl font-bold">11</h3>
                        </div>
                    </div>
                </div>

                <div className="bg-white p-6 rounded-xl border shadow-sm">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-purple-50 rounded-lg">
                            <BarChart className="w-6 h-6 text-purple-600" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 font-medium">Accuracy Rate</p>
                            <h3 className="text-2xl font-bold">98.5%</h3>
                        </div>
                    </div>
                </div>
            </div>

            <div>
                <h3 className="text-xl font-bold mb-4">Recent Activity</h3>
                <div className="bg-white border rounded-xl overflow-hidden">
                    <div className="p-6 text-center text-gray-500">
                        Visit the History tab to view full details
                    </div>
                </div>
            </div>
        </div>
    );
}
