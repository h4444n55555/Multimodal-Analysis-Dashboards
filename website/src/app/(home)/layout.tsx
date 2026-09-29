import { Footer } from "@/components/ui/footer-section";

/** The home page keeps the site footer; the data pages don't use one. */
export default function HomeLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <div className="flex flex-1 flex-col">{children}</div>
      <Footer />
    </>
  );
}
