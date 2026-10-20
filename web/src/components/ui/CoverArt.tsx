import { useEffect, useState } from "react";
import { getCoverUrl, getThumbUrl } from "../../api/client";

interface CoverArtProps {
  sha1: string;
  size: number;
  radius?: number;
  loading?: "lazy" | "eager";
  testId?: string;
}

/**
 * Capa com cantos arredondados.
 * Em web basta CSS border-radius + overflow:hidden — não precisa de canvas clip.
 * `loading` default "eager" preserva os usos da Revisao; a tabela da
 * Biblioteca passa "lazy" para nao baixar centenas de thumbs de uma vez.
 */
export function CoverArt({ sha1, size, radius = 6, loading = "eager", testId }: CoverArtProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setSrc(getThumbUrl(sha1));
    setError(false);
  }, [sha1]);

  const handleError = () => {
    // Fallback para capa original
    if (!error) {
      setError(true);
      setSrc(getCoverUrl(sha1));
    } else {
      setSrc(null);
    }
  };

  const placeholderClass = testId?.includes("inspector")
    ? "library-inspector-cover-empty"
    : "library-cover-empty";

  return (
    <div
      className="cover-art"
      style={{ width: size, height: size, borderRadius: radius }}
      data-testid={testId}
    >
      {src ? (
        <img
          src={src}
          alt=""
          width={size}
          height={size}
          loading={loading}
          onError={handleError}
          style={{ objectFit: "cover", width: "100%", height: "100%" }}
        />
      ) : (
        <div className={placeholderClass} aria-hidden="true" />
      )}
    </div>
  );
}
