import { Skeleton } from "@/components/ui/skeleton";

export function DashboardSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading analysis">
      <Skeleton className="h-44 w-full rounded-2xl" />
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        <Skeleton className="h-36 rounded-2xl" />
        <Skeleton className="h-36 rounded-2xl" />
        <Skeleton className="h-36 rounded-2xl" />
      </div>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Skeleton className="h-96 rounded-2xl" />
        <Skeleton className="h-96 rounded-2xl" />
        <Skeleton className="h-96 rounded-2xl" />
      </div>
      <Skeleton className="h-40 rounded-2xl" />
    </div>
  );
}
